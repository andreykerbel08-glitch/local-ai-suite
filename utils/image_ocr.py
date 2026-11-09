import cv2
from PIL import Image
import pytesseract


def enhanced_ocr(path: str) -> str:
    try:
        img = cv2.imread(path)
        if img is None:
            return "Не удалось открыть изображение."
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 3)
        text = pytesseract.image_to_string(gray, lang="rus+eng")
        return text.strip()
    except Exception as exc:
        return f"Ошибка OCR: {exc}"
