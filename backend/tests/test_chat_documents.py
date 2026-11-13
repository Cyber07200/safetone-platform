"""Chat: the bank-specific assistant and documents sent for checking."""
from __future__ import annotations

import io
import secrets

import httpx
import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import ChatMessage
from app.services.ai.router import set_router
from tests.helpers import body, chat_response, gigachat_router

OWNER = secrets.token_urlsafe(32)
H = {"X-Chat-Owner": OWNER}
CONTRACT = ("Индивидуальные условия по кредитной карте «Берег 120». "
            "Процентная ставка по операциям покупок — 39,9% годовых. "
            "Комиссия за снятие наличных в банкоматах любых банков — 3,9% от суммы + 390 ₽. "
            "Минимальный платёж — 3% от суммы задолженности, но не менее 300 ₽.")
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def upload(client, bank_id, name, data, mode="demo", content="", conv=None):
    form = {"bank_id": bank_id, "mode": mode, "content": content}
    if conv:
        form["conversation_id"] = conv
    return client.post("/api/v1/chat/documents", headers=H, data=form, files={"file": (name, data)})


@pytest.fixture()
def live():
    seen: list[httpx.Request] = []

    def make(reply="Разбор документа"):
        def handler(req: httpx.Request):
            seen.append(req)
            if req.url.path.endswith("/files"):
                return httpx.Response(200, json={"id": "file-123", "object": "file", "bytes": 72})
            if req.url.path.endswith("/delete"):
                return httpx.Response(200, json={"id": "file-123", "deleted": True})
            return chat_response(reply(body(req)) if callable(reply) else reply)
        r, _ = gigachat_router(handler)
        set_router(r)
        return seen
    yield make
    set_router(None)


def test_text_document_is_checked_against_bank_tariffs(client, bank_id):
    r = upload(client, bank_id, "условия.txt", CONTRACT.encode())
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["user_message"]["attachment"] == {"filename": "условия.txt", "kind": "txt", "size": len(CONTRACT.encode()),
                                               "chars": len(CONTRACT), "recognized_by": "text_layer",
                                               "truncated": False}
    assert d["user_message"]["content"] == "Проверь документ «условия.txt»"
    findings = d["assistant_message"]["findings"]
    wrong = next(f for f in findings if "39,9%" in f["text"])
    assert wrong["status"] == "CONTRADICTED" and "Берег 120" in wrong["source"] and "29,9%" in wrong["quote"]
    assert any(f["status"] == "CONFIRMED" and "390 ₽" in f["text"] for f in findings)
    assert "Расходится с условиями банка или законом: 1" in d["assistant_message"]["content"]


def test_word_document_is_read(client, bank_id):
    import docx
    doc = docx.Document()
    for line in CONTRACT.split(". "):
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    r = upload(client, bank_id, "договор.docx", buf.getvalue())
    assert r.status_code == 200, r.text
    assert r.json()["user_message"]["attachment"]["kind"] == "docx"
    assert any(f["status"] == "CONTRADICTED" for f in r.json()["assistant_message"]["findings"])


def test_photo_needs_gigachat(client, bank_id):
    r = upload(client, bank_id, "скан.png", PNG)
    assert r.status_code == 422 and r.json()["error"]["code"] == "OCR_UNAVAILABLE"


def test_fake_extension_is_rejected(client, bank_id):
    r = upload(client, bank_id, "фото.jpg", b"%PDF-1.4 not an image")
    assert r.status_code == 422 and r.json()["error"]["code"] == "FILE_SIGNATURE_MISMATCH"
    r = upload(client, bank_id, "virus.exe", b"MZ....")
    assert r.status_code == 422 and r.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_photo_is_transcribed_by_gigachat_and_deleted_there(client, bank_id, live):
    seen = live(reply=lambda b: CONTRACT if "Перепиши дословно" in b["messages"][0]["content"] else "Разбор: ставка 39,9% не совпадает с тарифом 29,9%.")
    r = upload(client, bank_id, "фото.png", PNG, mode="live", content="Проверь мой договор")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["user_message"]["attachment"]["recognized_by"] == "gigachat"
    paths = [q.url.path for q in seen]
    assert paths.index("/v1/files") < paths.index("/v1/files/file-123/delete")    # uploaded, then removed
    ocr = next(body(q) for q in seen if q.url.path.endswith("/chat/completions"))
    assert ocr["messages"][0]["attachments"] == ["file-123"]
    final = body([q for q in seen if q.url.path.endswith("/chat/completions")][-1])
    user = final["messages"][-1]["content"]
    assert "<document" in user and "39,9%" in user and "<findings>" in user and "[CONTRADICTED]" in user
    assert d["assistant_message"]["content"].startswith("Разбор")


def test_document_text_is_encrypted_and_remembered(client, bank_id, live):
    seen = live()
    conv = upload(client, bank_id, "условия.txt", CONTRACT.encode(), mode="live").json()["conversation"]["id"]
    s = SessionLocal()
    try:
        row = s.scalars(select(ChatMessage).where(ChatMessage.conversation_id == conv, ChatMessage.role == "user")).one()
        assert row.attachment_enc and "39,9" not in row.attachment_enc and "Берег" not in row.attachment_enc
    finally:
        s.close()
    client.post("/api/v1/chat/messages", headers=H,
                json={"bank_id": bank_id, "conversation_id": conv, "content": "А пункт про минимальный платёж нормальный?",
                      "mode": "live"})
    history = [m["content"] for m in body(seen[-1])["messages"]]
    assert any("<document" in c and "Минимальный платёж" in c for c in history)  # follow-up sees the document


def test_assistant_knows_its_bank_and_prefers_bank_rules(client, bank_id, live):
    seen = live()
    client.post("/api/v1/chat/messages", headers=H,
                json={"bank_id": bank_id, "content": "Сколько стоит снятие наличных с дебетовой карты в чужом банкомате?",
                      "mode": "live"})
    req = body(seen[-1])
    assert "Ясный Берег" in req["messages"][0]["content"] and "Дебетовая карта «Ясная»" in req["messages"][0]["content"]
    user = req["messages"][-1]["content"]
    assert user.index('kind="bank"') < user.index('kind="law"')
    assert "Тарифы по дебетовой карте «Ясная»" in user


def test_document_is_checked_against_its_own_product(client, bank_id):
    loan = ("Индивидуальные условия потребительского кредита «Простой». Процентная ставка — 21,9% годовых. "
            "За досрочное погашение кредита взимается комиссия 2% от суммы досрочного погашения.")
    findings = upload(client, bank_id, "кредит.txt", loan.encode()).json()["assistant_message"]["findings"]
    rate = next(f for f in findings if "21,9%" in f["text"])
    assert rate["status"] != "CONTRADICTED" or "Прибой" not in (rate["source"] or "")  # not a savings-account rate
    assert all("Прибой" not in (f["source"] or "") and "ипотечн" not in (f["source"] or "") for f in findings)
    fee = next(f for f in findings if "комиссия 2%" in f["text"])
    assert fee["status"] == "CONTRADICTED" and "«Простой»" in fee["source"]


def test_ocr_rouble_sign_is_normalised():
    from app.services.chat_files import normalize_ocr
    assert normalize_ocr("Сумма кредита — 300 000 Р. Плата 99Р, Ромашка 5 Роз") == \
        "Сумма кредита — 300 000 ₽. Плата 99 ₽, Ромашка 5 Роз"

