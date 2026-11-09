import copy
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import requests

from config import (
    COMFYUI_FRAMES_INPUT,
    COMFYUI_FRAMES_NODE_ID,
    COMFYUI_PROMPT_INPUT,
    COMFYUI_PROMPT_NODE_ID,
    COMFYUI_SEED_INPUT,
    COMFYUI_SEED_NODE_ID,
    COMFYUI_URL,
    COMFYUI_WORKFLOW,
    MAX_VIDEO_SECONDS,
    OUTPUT_DIR,
    VIDEO_FPS,
    VIDEO_GENERATION_TIMEOUT,
)

VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".mkv"}
POLL_SECONDS = 2
MAX_PROMPT_LENGTH = 2000
MAX_OUTPUT_BYTES = 1024 * 1024 * 1024

_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def _build_workflow(text: str, seed: int | None, duration_seconds: int) -> dict:
    if not text.strip() or len(text) > MAX_PROMPT_LENGTH:
        raise ValueError(f"Описание должно содержать 1–{MAX_PROMPT_LENGTH} символов.")
    if not 1 <= duration_seconds <= MAX_VIDEO_SECONDS:
        raise ValueError(f"Длительность должна быть от 1 до {MAX_VIDEO_SECONDS} секунд.")
    if VIDEO_FPS < 1 or VIDEO_FPS > 60:
        raise RuntimeError("VIDEO_FPS должен быть в диапазоне 1–60.")
    if not COMFYUI_PROMPT_NODE_ID or not COMFYUI_FRAMES_NODE_ID:
        raise RuntimeError(
            "Настройте COMFYUI_PROMPT_NODE_ID и COMFYUI_FRAMES_NODE_ID "
            "по ID узлов в API-workflow ComfyUI."
        )
    if not COMFYUI_WORKFLOW.is_file():
        raise RuntimeError(
            f"Не найден ComfyUI API-workflow: {COMFYUI_WORKFLOW}. "
            "Экспортируйте workflow в API format и укажите COMFYUI_WORKFLOW."
        )

    try:
        workflow = json.loads(COMFYUI_WORKFLOW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Не удалось загрузить workflow JSON: {exc}") from exc

    if not isinstance(workflow, dict) or not workflow:
        raise RuntimeError("Workflow пустой или имеет неверный формат.")
    workflow = copy.deepcopy(workflow)

    def set_input(node_id: str, input_name: str, value: Any, label: str) -> None:
        node = workflow.get(str(node_id))
        inputs = node.get("inputs") if isinstance(node, dict) else None
        if not isinstance(inputs, dict) or input_name not in inputs:
            raise RuntimeError(
                f"В API-workflow не найден {label}: узел {node_id}, вход {input_name}."
            )
        inputs[input_name] = value

    set_input(COMFYUI_PROMPT_NODE_ID, COMFYUI_PROMPT_INPUT, text.strip(), "вход текста")
    set_input(
        COMFYUI_FRAMES_NODE_ID,
        COMFYUI_FRAMES_INPUT,
        duration_seconds * VIDEO_FPS,
        "вход количества кадров",
    )
    if seed is not None:
        if seed < 0 or seed > 2**64 - 1:
            raise ValueError("Seed должен быть в диапазоне 0..2^64-1.")
        if not COMFYUI_SEED_NODE_ID:
            raise RuntimeError("Для передачи seed настройте COMFYUI_SEED_NODE_ID.")
        set_input(COMFYUI_SEED_NODE_ID, COMFYUI_SEED_INPUT, seed, "вход seed")

    return workflow


def create_video_job() -> dict:
    job_id = uuid.uuid4().hex
    job = {
        "id": job_id,
        "status": "queued",
        "message": "Задача ожидает запуска.",
        "error": None,
        "video_url": None,
    }
    with _jobs_lock:
        _jobs[job_id] = job
    return dict(job)


def get_video_job(job_id: str) -> dict | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def get_video_path(job_id: str) -> Path | None:
    with _jobs_lock:
        path_value = _jobs.get(job_id, {}).get("_path")
    if not path_value:
        return None
    path = Path(path_value)
    return path if path.is_file() else None


def _update_job(job_id: str, **fields: Any) -> None:
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(fields)


def _find_video_output(history_entry: dict) -> dict:
    for node_output in history_entry.get("outputs", {}).values():
        if not isinstance(node_output, dict):
            continue
        for key in ("videos", "gifs", "images"):
            items = node_output.get(key, [])
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict) and Path(item.get("filename", "")).suffix.lower() in VIDEO_EXTENSIONS:
                    return item
    raise RuntimeError("Workflow завершился, но не выдал видеофайл (.mp4/.webm/.mov/.mkv).")


def _download_output(output: dict, job_id: str) -> Path:
    filename = output.get("filename", "")
    if Path(filename).name != filename or Path(filename).suffix.lower() not in VIDEO_EXTENSIONS:
        raise RuntimeError("ComfyUI вернул недопустимое имя/формат видео.")

    response = requests.get(
        f"{COMFYUI_URL}/view",
        params={
            "filename": filename,
            "subfolder": output.get("subfolder", ""),
            "type": output.get("type", "output"),
        },
        stream=True,
        timeout=(10, 120),
    )
    response.raise_for_status()
    target_dir = OUTPUT_DIR / "generated"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{job_id}{Path(filename).suffix.lower()}"
    total = 0
    try:
        with target.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_OUTPUT_BYTES:
                    raise RuntimeError("Сгенерированный файл превышает лимит 1 GiB.")
                handle.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        response.close()
    if total == 0:
        target.unlink(missing_ok=True)
        raise RuntimeError("ComfyUI вернул пустой файл.")
    return target


def run_video_job(job_id: str, text: str, seed: int | None, duration_seconds: int) -> None:
    try:
        _update_job(job_id, status="running", message="Подготавливаю workflow.")
        workflow = _build_workflow(text, seed, duration_seconds)
        response = requests.post(f"{COMFYUI_URL}/prompt", json={"prompt": workflow}, timeout=(10, 60))
        response.raise_for_status()
        prompt_id = response.json().get("prompt_id")
        if not prompt_id:
            raise RuntimeError("ComfyUI не вернул prompt_id.")

        deadline = time.monotonic() + VIDEO_GENERATION_TIMEOUT
        while time.monotonic() < deadline:
            _update_job(job_id, message="ComfyUI генерирует видео.")
            time.sleep(POLL_SECONDS)
            history_response = requests.get(
                f"{COMFYUI_URL}/history/{prompt_id}", timeout=(10, 30)
            )
            history_response.raise_for_status()
            entry = history_response.json().get(prompt_id)
            if not entry:
                continue
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                raise RuntimeError(f"Ошибка workflow ComfyUI: {status.get('messages', [])}")
            try:
                output = _find_video_output(entry)
            except RuntimeError:
                continue
            path = _download_output(output, job_id)
            _update_job(
                job_id,
                status="completed",
                message="Видео готово.",
                video_url=f"/media/video/jobs/{job_id}/download",
                _path=str(path),
            )
            return
        raise TimeoutError("Истекло время ожидания генерации ComfyUI.")
    except Exception as exc:
        _update_job(job_id, status="failed", message="Генерация не удалась.", error=str(exc))
