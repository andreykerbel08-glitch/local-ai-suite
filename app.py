import io
import uuid
import zipfile
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from config import ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE, OUTPUT_DIR, STATIC_DIR, TEMP_DIR, UPLOAD_DIR, MAX_VIDEO_SECONDS
from utils.audio_transcriber import transcribe_audio
from utils.db import clear_history, get_history, init_db, save_message, save_upload_meta
from utils.file_parser import create_zip_from_uploaded, extract_text_by_extension, list_files
from utils.image_ocr import enhanced_ocr
from utils.local_llm import answer_user
from utils.media_service import (
    analyze_video,
    create_video_job,
    get_video_job,
    get_video_path,
    run_video_job,
)
from utils.safe_math import calculate
from utils.tts import speak_text
from utils.wiki_search import search_wikipedia

app = FastAPI(title="Local AI Assistant")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
init_db()


def get_uploaded_file(filename: str) -> Path:
    if not filename or Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="Некорректное имя файла.")
    root = UPLOAD_DIR.resolve()
    path = (root / filename).resolve()
    if path.parent != root or not path.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден.")
    return path


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    original_name = file.filename or ""
    extension = Path(original_name).suffix.lower()
    if not original_name:
        raise HTTPException(status_code=400, detail="Файл не выбран.")
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Неподдерживаемый тип файла: {extension}")

    filename = f"{uuid.uuid4().hex}{extension}"
    destination = UPLOAD_DIR / filename
    size = 0
    try:
        with destination.open("wb") as target:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE:
                    raise HTTPException(status_code=413, detail="Файл превышает лимит 25 MiB.")
                target.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    save_upload_meta(filename, extension, size)
    return {"status": "ok", "filename": filename, "size": size}


@app.get("/files")
def files_list():
    return {"files": list_files(str(UPLOAD_DIR))}


@app.get("/history")
def history():
    return {"history": get_history(limit=50)}


@app.post("/history/clear")
def clear_chat_history():
    clear_history()
    return {"status": "ok"}


@app.post("/ask")
async def ask_question(
    question: str = Form(...),
    selected_files: str = Form(""),
    wiki_on: str = Form("off"),
    image_on: str = Form("off"),
    audio_on: str = Form("off"),
):
    question = question.strip()
    if not question or len(question) > 4000:
        raise HTTPException(status_code=400, detail="Вопрос должен содержать 1–4000 символов.")

    docs, images, audios = [], [], []
    for name in filter(None, (item.strip() for item in selected_files.split(","))):
        path = get_uploaded_file(name)
        extracted = extract_text_by_extension(str(path))
        if extracted:
            docs.append(f"{name}:\n{extracted[:12000]}")
        if image_on == "on" and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            images.append(enhanced_ocr(str(path)))
        if audio_on == "on" and path.suffix.lower() in {".mp3", ".wav", ".ogg", ".m4a", ".flac"}:
            audios.append(transcribe_audio(str(path)))

    wiki = search_wikipedia(question) if wiki_on == "on" else ""
    save_message("user", question)
    try:
        answer = answer_user(question, "\n\n".join(docs), wiki, "\n".join(images), "\n".join(audios))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    save_message("assistant", answer)
    return {"answer": answer}


@app.post("/calc")
async def calc(expr: str = Form(...)):
    try:
        return {"result": calculate(expr)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/media/audio/transcribe")
async def media_audio_transcribe(filename: str = Form(...)):
    path = get_uploaded_file(filename)
    if path.suffix.lower() not in {".mp3", ".wav", ".ogg", ".m4a", ".flac"}:
        raise HTTPException(status_code=415, detail="Неподдерживаемый тип аудио.")
    try:
        return {"text": transcribe_audio(str(path))}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Ошибка распознавания: {exc}") from exc


@app.post("/media/video/analyze")
async def media_video_analyze(
    filename: str = Form(...),
    question: str = Form(...),
    frame_count: int = Form(6),
    include_audio: bool = Form(True),
):
    path = get_uploaded_file(filename)
    if path.suffix.lower() not in {".mp4", ".mov", ".mkv", ".webm", ".avi"}:
        raise HTTPException(status_code=415, detail="Неподдерживаемый тип видео.")
    if not 1 <= frame_count <= 8:
        raise HTTPException(status_code=400, detail="frame_count должен быть от 1 до 8.")
    try:
        return analyze_video(str(path), question, frame_count, include_audio)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/media/video/generate", status_code=202)
def media_video_generate(
    background_tasks: BackgroundTasks,
    text: str = Form(...),
    duration_seconds: int = Form(8),
    seed: int | None = Form(None),
):
    if not 1 <= duration_seconds <= MAX_VIDEO_SECONDS:
        raise HTTPException(status_code=400, detail=f"Длительность должна быть от 1 до {MAX_VIDEO_SECONDS} секунд.")
    if not text.strip() or len(text) > 2000:
        raise HTTPException(status_code=400, detail="Описание должно содержать 1–2000 символов.")
    job = create_video_job()
    background_tasks.add_task(run_video_job, job["id"], text.strip(), seed, duration_seconds)
    return job


@app.get("/media/video/jobs/{job_id}")
def video_job_status(job_id: str):
    job = get_video_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена.")
    job.pop("_path", None)
    return job


@app.get("/media/video/jobs/{job_id}/download")
def download_generated_video(job_id: str):
    job = get_video_job(job_id)
    path = get_video_path(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена.")
    if job.get("status") != "completed" or path is None:
        raise HTTPException(status_code=409, detail="Видео ещё не готово.")
    media_types = {".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime", ".mkv": "video/x-matroska"}
    return FileResponse(path, media_type=media_types[path.suffix.lower()], filename=f"generated-{job_id}{path.suffix}")


@app.post("/media/tts")
async def media_tts(text: str = Form(...)):
    if not text.strip() or len(text) > 5000:
        raise HTTPException(status_code=400, detail="Текст должен содержать 1–5000 символов.")
    output = TEMP_DIR / f"{uuid.uuid4().hex}.wav"
    try:
        path = speak_text(text.strip(), str(output))
        return FileResponse(path, media_type="audio/wav", filename="assistant-speech.wav")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/download-files.zip")
def download_zip():
    output_path = OUTPUT_DIR / "uploaded_bundle.zip"
    create_zip_from_uploaded(str(output_path), str(UPLOAD_DIR))
    return FileResponse(output_path, media_type="application/zip", filename=output_path.name)


@app.get("/download-project.zip")
def download_project_zip():
    root = Path(__file__).resolve().parent
    buffer = io.BytesIO()
    excluded = {".git", ".venv", "__pycache__", "output", "uploads", "temp"}
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in root.rglob("*"):
            if not path.is_file() or any(part in excluded for part in path.parts):
                continue
            if path.name == "ai_history.db" or (path.name.startswith(".") and path.name != ".gitignore"):
                continue
            archive.write(path, arcname=str(path.relative_to(root)))
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="project_bundle.zip"'})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
