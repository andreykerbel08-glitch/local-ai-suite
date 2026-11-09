import pyttsx3


def speak_text(text: str, output_path: str = "temp/voice_output.wav") -> str:
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 170)
        engine.setProperty("volume", 1.0)
        engine.save_to_file(text, output_path)
        engine.runAndWait()
        engine.stop()
        return output_path
    except Exception as exc:
        raise RuntimeError(f"Ошибка TTS: {exc}") from exc
