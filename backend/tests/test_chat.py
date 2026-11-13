"""Chat: encryption at rest, owner isolation, memory, knowledge-base access."""
from __future__ import annotations

import secrets

import httpx
import pytest
from sqlalchemy import select

from app.core import crypto
from app.db.session import SessionLocal
from app.models import BankSettings, ChatConversation, ChatMessage
from app.services.ai.router import set_router
from tests.helpers import body, chat_response, gigachat_router

OWNER = secrets.token_urlsafe(32)
STRANGER = secrets.token_urlsafe(32)


def h(token: str = OWNER) -> dict:
    return {"X-Chat-Owner": token}


def send(client, bank_id, content, conv=None, mode="demo", token=OWNER):
    return client.post("/api/v1/chat/messages", headers=h(token),
                       json={"bank_id": bank_id, "conversation_id": conv, "content": content, "mode": mode})


@pytest.fixture()
def live():
    seen: list[dict] = []

    def make(reply="Ответ GigaChat", **kw):
        def handler(req: httpx.Request):
            seen.append(body(req))
            return chat_response(reply if isinstance(reply, str) else reply(body(req)))
        r, _ = gigachat_router(handler, **kw)
        set_router(r)
        return seen
    yield make
    set_router(None)


def test_demo_answer_quotes_laws_and_is_stored(client, bank_id):
    r = send(client, bank_id, "Застрахованы ли вклады физических лиц и на какую сумму?")
    assert r.status_code == 200, r.text
    d = r.json()
    a = d["assistant_message"]
    assert a["mode"] == "demo" and a["content"].startswith("Демо-режим")
    assert any("177-ФЗ" in s["title"] for s in a["sources"])
    conv = client.get(f"/api/v1/chat/conversations/{d['conversation']['id']}", headers=h()).json()
    assert [m["role"] for m in conv["messages"]] == ["user", "assistant"]
    assert conv["messages"][0]["content"] == "Застрахованы ли вклады физических лиц и на какую сумму?"
    assert conv["title"].startswith("Застрахованы ли вклады")


def test_history_is_encrypted_at_rest(client, bank_id):
    secret_phrase = "мой долг 731 942 рубля перед банком Ясный Берег"
    conv_id = send(client, bank_id, secret_phrase).json()["conversation"]["id"]
    s = SessionLocal()
    try:
        conv = s.get(ChatConversation, conv_id)
        rows = s.scalars(select(ChatMessage).where(ChatMessage.conversation_id == conv_id)).all()
        raw = " ".join([conv.title_enc, conv.owner_hash] + [m.content_enc + (m.sources_enc or "") for m in rows])
        assert "731" not in raw and "долг" not in raw and OWNER not in raw
        assert all(m.content_enc.startswith("v1.") for m in rows)
        user = next(m for m in rows if m.role == "user")
        assert crypto.decrypt(conv_id, user.content_enc, f"{user.id}:user") == secret_phrase
        # Tampering or moving a ciphertext to another message / chat is detected, not silently accepted.
        bot = next(m for m in rows if m.role == "assistant")
        with pytest.raises(crypto.DecryptionFailed):
            crypto.decrypt(conv_id, user.content_enc, f"{bot.id}:user")
        with pytest.raises(crypto.DecryptionFailed):
            crypto.decrypt("other-conversation", user.content_enc, f"{user.id}:user")
        tampered = user.content_enc[:-4] + ("AAAA" if not user.content_enc.endswith("AAAA") else "BBBB")
        with pytest.raises(crypto.DecryptionFailed):
            crypto.decrypt(conv_id, tampered, f"{user.id}:user")
    finally:
        s.close()


def test_same_text_encrypts_differently():
    a, b = crypto.encrypt("c1", "одинаковый текст", "x"), crypto.encrypt("c1", "одинаковый текст", "x")
    assert a != b  # random nonce: equal messages are not recognisable in the database


def test_conversations_are_private_to_their_owner(client, bank_id):
    conv_id = send(client, bank_id, "Вопрос владельца").json()["conversation"]["id"]
    assert client.get(f"/api/v1/chat/conversations/{conv_id}", headers=h(STRANGER)).status_code == 404
    assert conv_id not in [c["id"] for c in client.get("/api/v1/chat/conversations", params={"bank_id": bank_id},
                                                        headers=h(STRANGER)).json()]
    assert send(client, bank_id, "чужое", conv=conv_id, token=STRANGER).status_code == 404
    assert client.delete(f"/api/v1/chat/conversations/{conv_id}", headers=h(STRANGER)).status_code == 404
    assert conv_id in [c["id"] for c in client.get("/api/v1/chat/conversations", params={"bank_id": bank_id},
                                                    headers=h()).json()]


def test_owner_token_is_validated(client, bank_id):
    assert client.get("/api/v1/chat/conversations", params={"bank_id": bank_id},
                      headers=h("short")).status_code == 422
    assert client.get("/api/v1/chat/conversations", params={"bank_id": bank_id}).status_code == 422


def test_rename_and_delete(client, bank_id):
    conv_id = send(client, bank_id, "Переименуй меня").json()["conversation"]["id"]
    r = client.patch(f"/api/v1/chat/conversations/{conv_id}", headers=h(), json={"title": "Вклады"})
    assert r.status_code == 200 and r.json()["title"] == "Вклады"
    assert client.delete(f"/api/v1/chat/conversations/{conv_id}", headers=h()).status_code == 204
    assert client.get(f"/api/v1/chat/conversations/{conv_id}", headers=h()).status_code == 404
    s = SessionLocal()
    try:
        assert not s.scalars(select(ChatMessage).where(ChatMessage.conversation_id == conv_id)).all()
    finally:
        s.close()


def test_live_unavailable_is_reported(client, bank_id):
    r = send(client, bank_id, "Привет", mode="live")
    assert r.status_code == 409 and r.json()["error"]["code"] == "LIVE_MODE_UNAVAILABLE"


def test_live_answer_gets_laws_and_remembers_dialog(client, bank_id, live):
    seen = live(reply="По 177-ФЗ возмещение — 100% вкладов, но не более 1 400 000 ₽.")
    first = send(client, bank_id, "Какая сумма вкладов застрахована?", mode="live").json()
    conv_id = first["conversation"]["id"]
    assert first["assistant_message"]["mode"] == "live" and first["assistant_message"]["model"] == "GigaChat-test"
    req1 = seen[-1]["messages"]
    assert "<source" in req1[-1]["content"] and "177-ФЗ" in req1[-1]["content"]  # GigaChat sees the law text

    send(client, bank_id, "А если у меня два вклада в этом банке?", conv=conv_id, mode="live")
    req2 = seen[-1]["messages"]
    contents = [m["content"] for m in req2]
    assert "Какая сумма вкладов застрахована?" in contents                      # remembers the question
    assert "По 177-ФЗ возмещение — 100% вкладов, но не более 1 400 000 ₽." in contents  # and its own answer
    assert [m["role"] for m in req2] == ["system", "user", "assistant", "user"]


def _share_docs(bank_id: str, flag: bool) -> None:
    s = SessionLocal()
    s.get(BankSettings, bank_id).allow_documents_to_llm = flag
    s.commit()
    s.close()


def test_bank_documents_reach_gigachat_only_with_permission(client, bank_id, live):
    seen = live()
    q = "Какая ставка по кредитной карте Берег 120 на покупки?"
    send(client, bank_id, q, mode="live")
    assert "Тарифы по кредитной карте" in seen[-1]["messages"][-1]["content"]  # fictional bank: allowed
    _share_docs(bank_id, False)
    try:
        send(client, bank_id, q, mode="live")
        assert "Тарифы по кредитной карте" not in seen[-1]["messages"][-1]["content"]
    finally:
        _share_docs(bank_id, True)


def test_old_messages_are_folded_into_encrypted_memory(client, bank_id, live, monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "chat_history_window", 4)
    seen = live(reply=lambda b: ("ПАМЯТЬ: пользователь спрашивал про вклад «Надёжный»"
                                 if "Сожми диалог" in b["messages"][0]["content"] else "ответ"))
    conv_id = None
    for i in range(5):
        conv_id = send(client, bank_id, f"Вопрос номер {i} про вклад", conv=conv_id, mode="live").json()["conversation"]["id"]
    s = SessionLocal()
    try:
        conv = s.get(ChatConversation, conv_id)
        assert conv.summary_enc and "ПАМЯТЬ" not in conv.summary_enc
        assert conv.summarized_upto > 0
    finally:
        s.close()
    send(client, bank_id, "Что я спрашивал в начале?", conv=conv_id, mode="live")
    last = next(r["messages"] for r in reversed(seen) if "Сожми диалог" not in r["messages"][0]["content"])
    assert "ПАМЯТЬ: пользователь спрашивал про вклад «Надёжный»" in last[0]["content"]
    assert len(last) <= 1 + 4 + 1  # system + window + new question
