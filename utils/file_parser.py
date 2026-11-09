from pathlib import Path

from bs4 import BeautifulSoup
from docx import Document
from pypdf import PdfReader


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def extract_pdf_text(path: str) -> str:
    try:
        reader = PdfReader(path)
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages.append(text)
        return "\n".join(pages)
    except Exception as exc:
        return f"Ошибка чтения PDF: {exc}"


def extract_docx_text(path: str) -> str:
    try:
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as exc:
        return f"Ошибка чтения DOCX: {exc}"


def extract_html_text(path: str) -> str:
    try:
        html = read_text(path)
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator="\n")
    except Exception as exc:
        return f"Ошибка чтения HTML: {exc}"


def extract_text_by_extension(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return extract_pdf_text(path)
    if ext == ".docx":
        return extract_docx_text(path)
    if ext in {".html", ".htm"}:
        return extract_html_text(path)
    if ext in {".txt", ".md", ".csv", ".json", ".yaml", ".yml"}:
        return read_text(path)
    return ""
