from pathlib import Path
import zipfile

from bs4 import BeautifulSoup
from docx import Document
from pypdf import PdfReader


def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def extract_pdf_text(path: str) -> str:
    try:
        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    except Exception as exc:
        return f"Ошибка чтения PDF: {exc}"


def extract_docx_text(path: str) -> str:
    try:
        document = Document(path)
        return "\n".join(p.text for p in document.paragraphs if p.text.strip())
    except Exception as exc:
        return f"Ошибка чтения DOCX: {exc}"


def extract_html_text(path: str) -> str:
    try:
        soup = BeautifulSoup(read_text(path), "html.parser")
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


def list_files(folder: str) -> list[str]:
    directory = Path(folder)
    if not directory.exists():
        return []
    return sorted(item.name for item in directory.iterdir() if item.is_file())


def create_zip_from_uploaded(output_zip: str, uploaded_folder: str) -> str:
    target = Path(output_zip)
    target.parent.mkdir(parents=True, exist_ok=True)
    root = Path(uploaded_folder).resolve()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in list_files(str(root)):
            path = (root / name).resolve()
            if path.parent == root and path.is_file():
                archive.write(path, arcname=name)
    return str(target)
