import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
STATIC_DIR = BASE_DIR / "static"
TEMP_DIR = BASE_DIR / "temp"
DB_PATH = BASE_DIR / "ai_history.db"

for folder in [UPLOAD_DIR, OUTPUT_DIR, STATIC_DIR, TEMP_DIR]:
    folder.mkdir(exist_ok=True)

MAX_UPLOAD_SIZE = 25 * 1024 * 1024
WIKIPEDIA_LANG = os.getenv("WIKIPEDIA_LANG", "ru")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "qwen2.5vl:3b")

ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".pdf", ".docx", ".html", ".htm",
    ".csv", ".json", ".yaml", ".yml",
    ".png", ".jpg", ".jpeg", ".webp", ".bmp",
    ".mp3", ".wav", ".ogg", ".m4a", ".flac",
    ".mp4", ".mov", ".mkv", ".webm", ".avi",
}

COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")
COMFYUI_PROMPT_NODE_ID = os.getenv("COMFYUI_PROMPT_NODE_ID", "")
COMFYUI_PROMPT_INPUT = os.getenv("COMFYUI_PROMPT_INPUT", "text")
COMFYUI_SEED_NODE_ID = os.getenv("COMFYUI_SEED_NODE_ID", "")
COMFYUI_SEED_INPUT = os.getenv("COMFYUI_SEED_INPUT", "seed")
VIDEO_SEGMENT_SECONDS = int(os.getenv("VIDEO_SEGMENT_SECONDS", "4"))
VIDEO_FPS = int(os.getenv("VIDEO_FPS", "16"))
MAX_VIDEO_SECONDS = int(os.getenv("MAX_VIDEO_SECONDS", "600"))
