# Local AI Suite

A local AI assistant with:
- document analysis for TXT, PDF, DOCX, HTML, CSV, JSON
- OCR for images
- transcription of audio
- analysis of uploaded video
- optional text-to-video generation through ComfyUI
- calculation tools
- local Ollama LLM integration
- web UI + mobile-friendly PWA shell
- export of uploaded files as ZIP

## Setup

1. Create a virtual environment and install dependencies:

   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
   pip install -r requirements.txt

2. Install system tools:
   - Tesseract OCR
   - FFmpeg
   - Ollama

3. Pull a local model:

   ollama pull qwen2.5
   ollama pull qwen2.5vl:3b

4. Start the app:

   python app.py

5. Open:

   http://127.0.0.1:8000

## Video generation

This project includes a separate video-generation component that works through ComfyUI.

Prerequisites:
- ComfyUI installed locally
- a compatible text-to-video workflow exported as JSON
- a matching model for the workflow

Place the exported workflow in `workflows/text_to_video_api.json` and update the IDs in `config.py`.

The app exposes endpoints for:
- `/media/video/analyze`
- `/media/video/generate`
- `/media/tts`

## Notes

- This is a local workflow; no hidden evasion of AI detection is included.
- Generation speed depends on GPU, model choice, workflow complexity, and running environment.
- Video generation is a separate module and not a universal one-click shortcut.
