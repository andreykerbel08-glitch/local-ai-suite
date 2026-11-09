import whisper


def transcribe_audio(path: str) -> str:
    try:
        model = whisper.load_model("base")
        result = model.transcribe(path, fp16=False)
        text = result.get("text", "").strip()
        return text if text else "Аудио распознано, но текста не найдено."
    except Exception as exc:
        return f"Ошибка распознавания аудио: {exc}"
