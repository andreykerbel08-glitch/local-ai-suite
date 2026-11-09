import base64
import json
import subprocess
import tempfile
import time
from pathlib import Path

import cv2
import requests

from config import OLLAMA_URL, OLLAMA_VISION_MODEL, COMFYUI_URL, COMFYUI_PROMPT_INPUT, COMFYUI_PROMPT_NODE_ID, COMFYUI_SEED_INPUT, COMFYUI_SEED_NODE_ID, VIDEO_SEGMENT_SECONDS, VIDEO_FPS


def transcribe_audio(audio_path: str) -> dict:
    from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio_path, vad_filter=True, beam_size=5)
    text = " ".join(part.text.strip() for part in segments if part.text.strip())
    return {
        "text": text,
        "language": info.language,
        "duration": info.duration,
    }


def extract_audio_from_video(video_path: str, wav_path: str) -> bool:
    result = subprocess.run(
        [
            "ffmpeg", "-nostdin", "-y",
            "-i", video_path,
            "-vn",
            "-ac", "1",
            "-ar", "16000",
            wav_path,
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return result.returncode == 0 and Path(wav_path).is_file() and Path(wav_path).stat().st_size > 0


def _encode_frame(frame) -> str:
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not ok:
        raise RuntimeError("Не удалось подготовить кадр.")
    return base64.b64encode(encoded.tobytes()).decode("ascii")


def _sample_frames(video_path: str, frame_count: int = 6):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError("Не удалось открыть видео.")

    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        if total_frames <= 0 or fps <= 0:
            raise ValueError("Не удалось определить длительность видео.")

        duration = total_frames / fps
        sample_points = [duration * (i + 0.5) / frame_count for i in range(frame_count)]
        frames = []

        for ts in sample_points:
            cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
            ok, frame = cap.read()
            if ok:
                frames.append((ts, _encode_frame(frame)))

        if not frames:
            raise ValueError("Не удалось извлечь кадры из видео.")
        return frames
    finally:
        cap.release()


def analyze_video(video_path: str, question: str, frame_count: int = 6, include_audio: bool = True) -> dict:
    frames = _sample_frames(video_path, frame_count=frame_count)

    transcript = ""
    audio_error = None
    if include_audio:
        with tempfile.TemporaryDirectory(prefix="ai-video-") as temp_dir:
            wav_path = str(Path(temp_dir) / "audio.wav")
            try:
                if extract_audio_from_video(video_path, wav_path):
                    transcript = transcribe_audio(wav_path)["text"]
            except Exception as exc:
                audio_error = f"Не удалось распознать аудио: {exc}"

    prompt = (
        "Проанализируй выбранные кадры видео. Отвечай только по изображению и речи. "
        "Если данных недостаточно, честно укажи это.\n\n"
        f"Вопрос: {question}"
    )
    if transcript:
        prompt += f"\n\nРечь из видео:\n{transcript[:12000]}"

    payload = {
        "model": OLLAMA_VISION_MODEL,
        "stream": False,
        "messages": [{
            "role": "user",
            "content": prompt,
            "images": [image for _, image in frames],
        }],
    }

    try:
        response = requests.post(f"{OLLAMA_URL.rstrip('/')}/api/chat", json=payload, timeout=180)
        response.raise_for_status()
        data = response.json()
        answer = data.get("message", {}).get("content", "").strip()
    except Exception as exc:
        raise RuntimeError(f"Не удалось выполнить vision-анализ: {exc}") from exc

    return {
        "answer": answer or "Ответ не найден.",
        "transcript": transcript,
        "audio_error": audio_error,
        "sampled_timestamps": [round(ts, 2) for ts, _ in frames],
    }


def _read_workflow(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_video_from_prompt(text: str, seed: int | None = None, duration_seconds: int = 8):
    if not COMFYUI_PROMPT_NODE_ID:
        raise RuntimeError("COMFYUI_PROMPT_NODE_ID не настроен.")

    workflow_path = Path("workflows") / "text_to_video_api.json"
    if not workflow_path.is_file():
        raise RuntimeError(
            f"Не найден workflow: {workflow_path}. "
            "Сохраните JSON workflow из ComfyUI в папку workflows/."
        )

    workflow = _read_workflow(str(workflow_path))
    prompt_node = workflow.get(str(COMFYUI_PROMPT_NODE_ID))
    if not isinstance(prompt_node, dict):
        raise RuntimeError(f"Узел {COMFYUI_PROMPT_NODE_ID} не найден в workflow.")

    if COMFYUI_PROMPT_INPUT not in prompt_node.get("inputs", {}):
        raise RuntimeError(f"В prompt-узле нет input {COMFYUI_PROMPT_INPUT}.")
    prompt_node["inputs"][COMFYUI_PROMPT_INPUT] = text

    if seed is not None and COMFYUI_SEED_NODE_ID:
        seed_node = workflow.get(str(COMFYUI_SEED_NODE_ID))
        if not isinstance(seed_node, dict):
            raise RuntimeError(f"Узел {COMFYUI_SEED_NODE_ID} не найден в workflow.")
        if COMFYUI_SEED_INPUT not in seed_node.get("inputs", {}):
            raise RuntimeError(f"В узле seed нет input {COMFYUI_SEED_INPUT}.")
        seed_node["inputs"][COMFYUI_SEED_INPUT] = seed

    response = requests.post(f"{COMFYUI_URL.rstrip('/')}/prompt", json={"prompt": workflow}, timeout=(10, 60))
    response.raise_for_status()
    result = response.json()
    prompt_id = result.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI не вернул prompt_id: {result}")

    deadline = time.monotonic() + 30 * 60
    while time.monotonic() < deadline:
        history_response = requests.get(f"{COMFYUI_URL.rstrip('/')}/history/{prompt_id}", timeout=(10, 30))
        history_response.raise_for_status()
        history = history_response.json()
        entry = history.get(prompt_id)
        if not entry:
            time.sleep(3)
            continue

        outputs = entry.get("outputs", {})
        for node in outputs.values():
            if not isinstance(node, dict):
                continue
            for key in ("videos", "gifs", "images"):
                items = node.get(key, [])
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    filename = item.get("filename")
                    if not filename:
                        continue
                    output_dir = Path("output") / "generated"
                    output_dir.mkdir(parents=True, exist_ok=True)
                    final_path = output_dir / f"{prompt_id}{Path(filename).suffix}"
                    file_response = requests.get(
                        f"{COMFYUI_URL.rstrip('/')}/view",
                        params={
                            "filename": filename,
                            "subfolder": item.get("subfolder", ""),
                            "type": item.get("type", "output"),
                        },
                        stream=True,
                        timeout=(10, 120),
                    )
                    file_response.raise_for_status()
                    with final_path.open("wb") as fh:
                        for chunk in file_response.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                fh.write(chunk)
                    return {"status": "completed", "video_path": str(final_path)}
        time.sleep(3)

    raise TimeoutError("ComfyUI не завершил генерацию видео в отведённое время.")
