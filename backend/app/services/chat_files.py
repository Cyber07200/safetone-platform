"""Documents a user sends to the assistant for checking.

PDF / DOCX / TXT / MD / HTML are read locally (app/services/knowledge/extract.py).
Photos (JPG, PNG) and scanned PDFs without a text layer are transcribed by
GigaChat; the file is deleted from GigaChat right after. SafeTone keeps only
the recognised text, encrypted, never the file itself.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from app.core.config import get_settings
from app.core.errors import ValidationFailed
from app.services.ai.providers import GigaChatProvider
from app.services.knowledge.extract import detect_kind, extract_text
from app.services.knowledge.ingest import safe_filename

IMAGES = {"jpg": (b"\xff\xd8\xff", "image/jpeg"), "jpeg": (b"\xff\xd8\xff", "image/jpeg"),
          "png": (b"\x89PNG\r\n\x1a\n", "image/png")}
MAX_STORED_CHARS = 60_000
UNREADABLE = "ТЕКСТ НЕ РАСПОЗНАН"


@dataclass
class Attachment:
    filename: str
    kind: str          # pdf | docx | txt | md | html | jpg | png
    size: int
    text: str
    recognized_by: str  # text_layer | gigachat
    truncated: bool = False

    def public(self) -> dict:
        d = asdict(self)
        d.pop("text")
        d["chars"] = len(self.text)
        return d


async def read_attachment(filename: str, data: bytes, gigachat: GigaChatProvider | None) -> Attachment:
    cfg = get_settings()
    if not data:
        raise ValidationFailed("Файл пуст", code="EMPTY_DOCUMENT")
    if len(data) > cfg.max_upload_bytes:
        raise ValidationFailed(f"Файл больше {cfg.max_upload_bytes // (1024 * 1024)} МБ", code="FILE_TOO_LARGE")
    name = safe_filename(filename)
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""

    if ext in IMAGES:
        sig, mime = IMAGES[ext]
        if not data.startswith(sig):
            raise ValidationFailed("Содержимое файла не соответствует формату изображения",
                                   code="FILE_SIGNATURE_MISMATCH")
        return _finish(name, "png" if ext == "png" else "jpg", data, await _ocr(gigachat, data, name, mime),
                       "gigachat")

    kind = detect_kind(name, data)
    try:
        text = "\n\n".join(p.text for p in extract_text(kind, data))
    except ValidationFailed as exc:
        if kind == "pdf" and exc.code == "EMPTY_DOCUMENT":  # a scan: no text layer
            return _finish(name, kind, data, await _ocr(gigachat, data, name, "application/pdf"), "gigachat")
        raise
    return _finish(name, kind, data, text, "text_layer")


async def _ocr(gigachat: GigaChatProvider | None, data: bytes, name: str, mime: str) -> str:
    if gigachat is None or not gigachat.is_configured():
        raise ValidationFailed("Фото и сканы распознаёт GigaChat, а он не подключён. Отправьте PDF с текстом "
                               "или документ Word.", code="OCR_UNAVAILABLE")
    return normalize_ocr(await gigachat.transcribe(data, name, mime))


def normalize_ocr(text: str) -> str:
    # OCR reads the rouble sign as the letter «Р»: «300 000 Р» -> «300 000 ₽», so amounts are recognised.
    return re.sub(r"(\d)\s*[РP](?=[\s.,;:)]|$)", r"\1 ₽", text)


def _finish(name: str, kind: str, data: bytes, text: str, how: str) -> Attachment:
    text = text.strip()
    if len(text) < 20 or text.upper().startswith(UNREADABLE):
        raise ValidationFailed("Не удалось распознать текст документа. Сфотографируйте его ровно, при хорошем "
                               "освещении, или пришлите PDF / Word.", code="DOCUMENT_UNREADABLE")
    return Attachment(name, kind, len(data), text[:MAX_STORED_CHARS], how, len(text) > MAX_STORED_CHARS)
