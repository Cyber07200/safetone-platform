"""Download current texts of banking laws from base.garant.ru into app/seed/laws/*.md.

Laws are not subject to copyright in Russia (ГК РФ ст. 1259 п. 6), Garant only
mirrors the official text. Run from backend/:  python scripts/fetch_laws.py
Then restart the backend — new/changed laws are re-ingested by `seed_laws`.
The official source remains pravo.gov.ru; the file header records the date.
"""
from __future__ import annotations

import html
import re
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "app" / "seed" / "laws"
BASE = "https://base.garant.ru"

# key, garant id, title, date of adoption, chapter filter (None = whole law)
LAWS = [
    ("law-395-1", 10105800, "Федеральный закон от 02.12.1990 № 395-1 «О банках и банковской деятельности»", "1990-12-02", None),
    ("law-353-fz", 70544866, "Федеральный закон от 21.12.2013 № 353-ФЗ «О потребительском кредите (займе)»", "2013-12-21", None),
    ("law-177-fz", 12133717, "Федеральный закон от 23.12.2003 № 177-ФЗ «О страховании вкладов в банках Российской Федерации»", "2003-12-23", None),
    ("law-161-fz", 12187279, "Федеральный закон от 27.06.2011 № 161-ФЗ «О национальной платежной системе»", "2011-06-27", None),
    ("law-230-fz", 71433918, "Федеральный закон от 03.07.2016 № 230-ФЗ «О защите прав и законных интересов физических лиц при осуществлении деятельности по возврату просроченной задолженности»", "2016-07-03", None),
    ("law-2300-1", 10106035, "Закон РФ от 07.02.1992 № 2300-1 «О защите прав потребителей»", "1992-02-07", None),
    ("gk-rf-ch-42-44-45", 10164072, "Гражданский кодекс РФ (часть вторая): глава 42 «Заем и кредит», глава 44 «Банковский вклад», глава 45 «Банковский счет»", "1996-01-26",
     re.compile(r"^(Часть вторая|Раздел IV\.|Глава (42|44|45)\.)")),
]

ARTICLE = re.compile(r"^Статья \d")


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("cp1251", "replace")
        except OSError:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def links(page: str, doc_id: int) -> list[tuple[str, str]]:
    out = []
    for href, text in re.findall(rf'href="(?:{BASE})?(/{doc_id}/[0-9a-f]{{32}}/)"[^>]*>(.*?)</a>', page, re.S):
        label = html.unescape(re.sub(r"<[^>]+>", "", text)).replace("\xa0", " ")
        out.append((href, re.sub(r"\s+", " ", label).strip()))
    return out


def article_links(doc_id: int, chapter_filter: re.Pattern | None) -> list[tuple[str, str]]:
    seen: dict[str, str] = {}
    queue, visited = [(f"/{doc_id}/", "")], set()
    while queue:
        url, label = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        page = get(BASE + url)
        time.sleep(0.3)
        # With a chapter filter, take articles only from the selected chapter pages.
        take = chapter_filter is None or label.startswith("Глава")
        for href, text in links(page, doc_id):
            if ARTICLE.match(text):
                if take:
                    seen.setdefault(href, text)
            elif chapter_filter is not None and chapter_filter.match(text):
                queue.append((href, text))
            elif chapter_filter is None and text.startswith("Глава") and len(visited) < 80:
                queue.append((href, text))  # some laws list articles only inside chapter pages
    return list(seen.items())


def article_text(page: str) -> tuple[str, list[str]]:
    start = page.find('<div id="doc_content">')
    content = page[start: page.find("</section>", start)]
    heading, body = "", []
    for cls, inner in re.findall(r'<p[^>]*class="(s_15|s_1|s_52)"[^>]*>(.*?)</p>', content, re.S):
        text = html.unescape(re.sub(r"<[^>]+>", "", inner)).replace("\xa0", " ").strip()
        text = re.sub(r"\s+", " ", text)
        if not text:
            continue
        if cls == "s_15" and not heading:
            heading = text
        else:
            body.append(text)
    return heading, body


def fetch(key: str, doc_id: int, title: str, adopted: str, chapter_filter) -> Path:
    arts = article_links(doc_id, chapter_filter)
    if not arts:
        raise RuntimeError(f"{key}: no articles found")
    today = date.today().strftime("%d.%m.%Y")
    lines = [f"# {title}", "",
             f"Текст в действующей редакции по данным справочной системы ГАРАНТ ({BASE}/{doc_id}/) на {today}. "
             "Официальный источник — Официальный интернет-портал правовой информации pravo.gov.ru.", ""]
    empty = []
    for href, label in arts:
        heading, body = article_text(get(BASE + href))
        time.sleep(0.3)
        if not body and not re.search(r"\((утратил|не применя|исключ)", label):  # repealed articles have no text
            empty.append(label)
        lines += [f"## {heading or label}", "", *[f"{p}\n" for p in body]]
    if empty:  # the site sometimes serves a stub page instead of the article
        raise RuntimeError(f"{key}: пустые статьи, повторите загрузку: {empty[:5]}")
    path = OUT / f"{key}.md"
    path.write_text("\n".join(lines).rstrip() + "\n", "utf-8")
    meta = OUT / f"{key}.meta"
    meta.write_text(f"title={title}\nadopted={adopted}\nsource_url={BASE}/{doc_id}/\nfetched={date.today().isoformat()}\n", "utf-8")
    print(f"{key}: {len(arts)} статей, {path.stat().st_size // 1024} КБ", flush=True)
    return path


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    only = set(sys.argv[1:])
    for law in LAWS:
        if not only or law[0] in only:
            fetch(*law)
