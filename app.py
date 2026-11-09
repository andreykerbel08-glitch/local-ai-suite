import io
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from config import ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE, OUTPUT_DIR, STATIC_DIR, TEMP_DIR, UPLOAD_DIR
from utils.audio_transcriber import transcribe_audio
from utils.db import clear_history, get_history, init_db, save_message, save_upload_meta
from utils.file_parser import create_zip_from_uploaded, extract_text_by_extension, list_files
from utils.image_ocr import enhanced_ocr
from utils.local_llm import answer_user
from utils.media_service import analyze_video, generate_video_from_prompt
from utils.safe_math import calculate
from utils.tts import speak_text
from utils.wiki_search import search_wikipedia

app = FastAPI(title="Local AI Assistant")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

init_db()


def get_uploaded_file(filename: str) -> Path:
    if not filename or Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="Некorektное имя файла.")

    root = UPLOAD_DIR.resolve()
    path = (root / filename).resolve()

    if path.parent != root or not path.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден.")
    return path


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    original_name = file.filename or ""
    if not original_name:
        raise HTTPException(status_code=400, detail="Файл не выбран.")

    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Неподдерживаемый тип файла: {extension}")

    unique_name = f"{uuid4_hex()}{extension}"
    destination = UPLOAD_DIR / unique_name
    size = 0

    try:
        with destination.open("wb") as target:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE:
                    raise HTTPException(status_code=413, detail="Размер файла превышает лимит 25 МБ.")
                target.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    save_upload_meta(unique_name, extension, size)
    return {"status": "ok", "filename": unique_name, "size": size}


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
    if not question:
        raise HTTPException(status_code=400, detail="Введите вопрос.")
    save_message("user", question)

    file_names = [name.strip() for name in selected_files.split(",") if name.strip()]
    docs_text = ""
    image_text = ""
    audio_text = ""

    for name in file_names:
        path = get_uploaded_file(name)
        docs_text += "\n" + extract_text_by_extension(str(path))

        if image_on == "on" and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            image_text += "\n" + enhanced_ocr(str(path))

        if audio_on == "on" and path.suffix.lower() in {".mp3", ".wav", ".ogg", ".m4a", ".flac"}:
            audio_text += "\n" + transcribe_audio(str(path))

    wiki_text = ""
    if wiki_on == "on":
        wiki_text = search_wikipedia(question)

    try:
        answer = answer_user(question, docs_text, wiki_text, image_text, audio_text)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    save_message("assistant", answer)
    return {"answer": answer}


@app.post("/calc")
async def calc(expr: str = Form(...)):
    try:
        result = calculate(expr)
        return {"result": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/media/audio/transcribe")
async def media_audio_transcribe(filename: str = Form(...)):
    path = get_uploaded_file(filename)
    if path.suffix.lower() not in {".mp3", ".wav", ".ogg", ".m4a", ".flac"}:
        raise HTTPException(status_code=415, detail="Неподдерживаемый тип аудио.")

    try:
        return transcribe_audio(str(path))
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
    if not question.strip():
        raise HTTPException(status_code=400, detail="Введите вопрос о видео.")

    try:
        return analyze_video(str(path), question, frame_count=frame_count, include_audio=include_audio)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/media/video/generate")
async def media_video_generate(
    text: str = Form(...),
    seed: int | None = Form(None),
    duration_seconds: int = Form(8),
):
    if not text.strip():
        raise HTTPException(status_code=400, detail="Введите описание для генерации.")
    if duration_seconds < 1:
        raise HTTPException(status_code=400, detail="Длительность должна быть больше 0.")

    try:
        return generate_video_from_prompt(text=text.strip(), seed=seed, duration_seconds=duration_seconds)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/media/tts")
async def media_tts(text: str = Form(...)):
    try:
        output_path = str(TEMP_DIR / "voice_output.wav")
        path = speak_text(text, output_path)
        return FileResponse(path, media_type="audio/wav", filename="assistant-speech.wav")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/download-files.zip")
def download_zip():
    output_path = str(OUTPUT_DIR / "uploaded_bundle.zip")
    create_zip_from_uploaded(output_path, str(UPLOAD_DIR))
    return FileResponse(output_path, media_type="application/zip", filename="uploaded_bundle.zip")


@app.get("/download-project.zip")
def download_project_zip():
    root = Path(__file__).resolve().parent
    output = root / "output" / "project_bundle.zip"
    buffer = io.BytesIO()

    exclude_dirs = {".git", ".venv", "__pycache__", "output", "uploads", "temp"}
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in root.rglob("*"):
            if path.is_dir():
                if path.name in exclude_dirs:
                    continue
                continue

            if ".venv" in path.parts or "__pycache__" in path.parts:
                continue
            if path.name.startswith(".") and path.name != ".gitignore":
                continue

            rel = path.relative_to(root)
            archive.write(path, arcname=str(rel))

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="project_bundle.zip"'},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)


def uuid4_hex() -> str:
    import uuid
    return uuid.uuid4().hex
