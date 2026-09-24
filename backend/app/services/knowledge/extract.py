"""Safe text extraction from uploaded documents.

- Only whitelisted formats: PDF, DOCX, HTML, TXT, MD.
- File type is checked by extension AND content signature (magic bytes).
- Nothing from a document is ever executed: HTML scripts/styles are
  dropped, DOCX is read as XML via python-docx, PDF text via pypdf.
"""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass

from app.core.errors import ValidationFailed

ALLOWED = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "html": "text/html",
    "htm": "text/html",
    "txt": "text/plain",
    "md": "text/markdown",
}


@dataclass
class ExtractedPage:
    text: str
    page: int | None = None


def detect_kind(filename: str, data: bytes) -> str:
    if "." not in filename:
        raise ValidationFailed("У файла нет расширения", code="UNSUPPORTED_FILE_TYPE")
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED:
        raise ValidationFailed(
            f"Формат .{ext} не поддерживается. Допустимо: PDF, DOCX, HTML, TXT, MD",
            code="UNSUPPORTED_FILE_TYPE")
    if ext == "pdf" and not data.startswith(b"%PDF-"):
        raise ValidationFailed("Содержимое файла не соответствует формату PDF", code="FILE_SIGNATURE_MISMATCH")
    if ext == "docx":
        if not data.startswith(b"PK\x03\x04"):
            raise ValidationFailed("Содержимое файла не соответствует формату DOCX", code="FILE_SIGNATURE_MISMATCH")
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                names = zf.namelist()
                if "word/document.xml" not in names:
                    raise ValidationFailed("Архив не является документом DOCX", code="FILE_SIGNATURE_MISMATCH")
                # zip-bomb guard
                total = sum(i.file_size for i in zf.infolist())
                if total > 200 * 1024 * 1024:
                    raise ValidationFailed("DOCX слишком велик после распаковки", code="FILE_TOO_LARGE")
        except zipfile.BadZipFile as exc:
            raise ValidationFailed("Повреждённый DOCX", code="FILE_SIGNATURE_MISMATCH") from exc
    if ext in ("txt", "md", "html", "htm"):
        if b"\x00" in data[:4096]:
            raise ValidationFailed("Текстовый файл содержит двоичные данные", code="FILE_SIGNATURE_MISMATCH")
    return "html" if ext == "htm" else ext


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1251"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def extract_text(kind: str, data: bytes) -> list[ExtractedPage]:
    if kind == "pdf":
        from pypdf import PdfReader
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise ValidationFailed("Зашифрованные PDF не поддерживаются", code="ENCRYPTED_PDF")
            pages = [ExtractedPage((p.extract_text() or "").strip(), i + 1) for i, p in enumerate(reader.pages)]
        except ValidationFailed:
            raise
        except Exception as exc:
            raise ValidationFailed("Не удалось прочитать PDF", code="PDF_PARSE_ERROR") from exc
        pages = [p for p in pages if p.text]
        if not pages:
            raise ValidationFailed("В PDF не найден текстовый слой (сканы без OCR не поддерживаются)",
                                   code="EMPTY_DOCUMENT")
        return pages
    if kind == "docx":
        import docx
        try:
            d = docx.Document(io.BytesIO(data))
        except Exception as exc:
            raise ValidationFailed("Не удалось прочитать DOCX", code="DOCX_PARSE_ERROR") from exc
        lines = []
        for p in d.paragraphs:
            t = p.text.strip()
            if not t:
                continue
            style = (p.style.name or "").lower() if p.style is not None else ""
            lines.append(f"## {t}" if style.startswith("heading") or style.startswith("заголов") else t)
        for table in d.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    lines.append(" — ".join(dict.fromkeys(cells)))
        return [ExtractedPage("\n".join(lines))]
    if kind == "html":
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(_decode(data), "html.parser")
        for tag in soup(["script", "style", "noscript", "iframe", "object", "embed", "form"]):
            tag.decompose()
        for h in soup.find_all(["h1", "h2", "h3", "h4"]):
            h.replace_with("\n## " + h.get_text(" ", strip=True) + "\n")
        text = soup.get_text("\n")
        return [ExtractedPage("\n".join(l.strip() for l in text.splitlines() if l.strip()))]
    return [ExtractedPage(_decode(data))]
