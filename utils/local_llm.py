import requests

from config import OLLAMA_MODEL, OLLAMA_URL


def ask_local_model(prompt: str) -> str:
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": "Ты — полезный локальный помощник. Отвечай на языке пользователя. Не придумывай факты."},
                {"role": "user", "content": prompt},
            ],
        }
        response = requests.post(f"{OLLAMA_URL.rstrip('/')}/api/chat", json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        answer = data.get("message", {}).get("content", "").strip()
        if not answer:
            raise RuntimeError("Модель вернула пустой ответ.")
        return answer
    except Exception as exc:
        raise RuntimeError(f"Не удалось подключиться к Ollama: {exc}") from exc


def answer_user(question: str, docs_text: str = "", wiki_text: str = "", image_text: str = "", audio_text: str = "") -> str:
    context_parts = []

    for label, text in (
        ("Документы", docs_text),
        ("Википедия", wiki_text),
        ("Текст из изображения", image_text),
        ("Транскрипция аудио", audio_text),
    ):
        if text and text.strip():
            context_parts.append(f"### {label}\n{text[:10000]}")

    context = "\n\n".join(context_parts) or "Контекст отсутствует."
    prompt = f"""
    Ты — локальный AI-ассистент.
    Используй только доступный контекст. Не придумывай факты.
    Если информации недостаточно — честно скажи это.

    Контекст:
    {context}

    Вопрос:
    {question}
    """
    return ask_local_model(prompt)
