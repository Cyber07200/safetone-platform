"""Split document text into clause-level chunks with section references."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .extract import ExtractedPage

_CLAUSE_NO = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(?=\S)")
_HEADING = re.compile(r"^#{1,4}\s+(.*)$")

# Prompt-injection indicators inside *documents*. A match does not reject
# the document; it marks the chunk as suspicious so that it is never sent
# to an external LLM as context and is highlighted in the Knowledge Base.
_INJECTION = re.compile(
    r"(ignore\s+(all\s+)?(previous|prior|above)\s+instructions|disregard\s+the\s+(system|above)|"
    r"system\s*prompt|you\s+are\s+now\s+|act\s+as\s+|"
    r"игнорируй\w*\s+(все\s+)?(предыдущ|прошл|вышеуказ)\w*|забудь\w*\s+(все\s+)?(инструкц|правил)\w*|"
    r"системн\w+\s+(промпт|инструкц)\w*|ты\s+теперь\s+|отвечай\s+всегда\s+|"
    r"<\s*/?\s*(system|assistant|instructions?)\s*>)",
    re.I,
)


@dataclass
class ChunkDraft:
    ordinal: int
    section: str
    page: int | None
    text: str
    suspicious: bool


def looks_like_injection(text: str) -> bool:
    return bool(_INJECTION.search(text))


def chunk_pages(pages: list[ExtractedPage], *, target_chars: int = 700) -> list[ChunkDraft]:
    drafts: list[ChunkDraft] = []
    heading = ""
    buf: list[str] = []
    buf_section = ""
    buf_page: int | None = None

    def flush():
        nonlocal buf
        text = " ".join(buf).strip()
        if text:
            drafts.append(ChunkDraft(len(drafts), buf_section, buf_page, text, looks_like_injection(text)))
        buf = []

    for page in pages:
        for raw in page.text.splitlines():
            line = raw.strip()
            if not line:
                continue
            h = _HEADING.match(line)
            if h:
                flush()
                heading = h.group(1).strip()
                continue
            clause = _CLAUSE_NO.match(line)
            section = heading
            if clause:
                section = f"{heading} · п. {clause.group(1)}" if heading else f"п. {clause.group(1)}"
            # a numbered clause always starts a new chunk; otherwise grow to target size
            if clause or not buf or sum(len(b) for b in buf) + len(line) > target_chars or buf_page != page.page:
                flush()
                buf_section, buf_page = section, page.page
            buf.append(line)
    flush()
    return drafts
