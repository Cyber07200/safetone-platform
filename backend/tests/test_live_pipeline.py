"""Live Mode pipeline with mocked providers (mandatory scenario 7 and more)."""
from __future__ import annotations

import json

import httpx
import pytest

from app.db.session import SessionLocal
from app.models import BankSettings
from app.services.ai.router import set_router
from tests.conftest import process
from tests.helpers import body, chat_response, gigachat_router


@pytest.fixture()
def live(request):
    routers = []

    def make(handler, **kw):
        r, p = gigachat_router(handler, **kw)
        set_router(r)
        routers.append(r)
        return r
    yield make
    set_router(None)


def _set_docs_to_llm(bank_id: str, flag: bool) -> None:
    s = SessionLocal()
    s.get(BankSettings, bank_id).allow_documents_to_llm = flag
    s.commit()
    s.close()


@pytest.fixture(autouse=True)
def documents_not_shared_by_default(bank_id):
    # The demo bank allows it out of the box; these tests start from the conservative default.
    _set_docs_to_llm(bank_id, False)
    yield
    _set_docs_to_llm(bank_id, True)


@pytest.fixture()
def docs_to_llm(bank_id):
    yield lambda flag: _set_docs_to_llm(bank_id, flag)


def _route(gen_text: str, verify: dict | str | None = None, rewrite: str | None = None, fail_on: str | None = None):
    seen = []

    def handler(req: httpx.Request):
        b = body(req)
        system = b["messages"][0]["content"]
        kind = ("verify" if "юрист-верификатор" in system else "rewrite" if "редактор" in system else "generate")
        seen.append((kind, b))
        if fail_on == kind:
            return httpx.Response(503)
        if kind == "generate":
            return chat_response(gen_text)
        if kind == "verify":
            return chat_response(verify if isinstance(verify, str) else json.dumps(verify or {"claims": []}))
        return chat_response(rewrite if rewrite is not None else b["messages"][1]["content"]
                               .split("\n", 1)[1].rsplit("\n", 1)[0])
    return handler, seen


def test_live_generation_is_verified_and_attributed(client, bank_id, products, live):
    handler, seen = _route("Процентная ставка по операциям покупок — 19,9% годовых.",
                           rewrite="Ставка по покупкам — 29,9% годовых.")
    live(handler)
    d = process(client, bank_id, mode="live", question="Ставка по карте?",
                product_id=products["card-bereg-120"]).json()
    assert d["execution_status"] == "completed"
    assert d["answer_origin"] == "provider" and d["provider"] == "gigachat" and d["model"] == "GigaChat-test"
    assert d["original_answer"].startswith("Процентная ставка") and "19,9%" in d["original_answer"]
    assert "29,9%" in d["legal_answer"]
    assert d["final_answer"] == "Ставка по покупкам — 29,9% годовых."
    assert d["linguistic"]["method"] == "llm:gigachat"
    assert d["tokens_total"] == 84 and len(d["ai_calls"]) == 2
    assert not any("DEMO" in n for n in d["notices"])
    # bank documents were NOT sent (setting is off by default)
    gen_body = next(b for k, b in seen if k == "generate")
    assert "<source" not in gen_body["messages"][1]["content"]
    assert "verify" not in [k for k, _ in seen]
    ver = next(s for s in d["stages"] if s["key"] == "legal_verification")
    assert any("отключена" in w for w in ver["warnings"])


# 7. Ошибка API не отображается как успешная обработка -------------------------------
def test_provider_failure_marks_run_failed(client, bank_id, live):
    handler, _ = _route("x", fail_on="generate")
    live(handler)
    d = process(client, bank_id, mode="live", question="Какая ставка?").json()
    assert d["result_status"] == "FAILED" and d["execution_status"] == "failed"
    assert d["final_answer"] is None
    assert d["error"]["code"] == "ALL_PROVIDERS_FAILED" and d["error"]["stage"] == "generation"
    st = {s["key"]: s["status"] for s in d["stages"]}
    assert st["generation"] == "failed"
    assert all(v == "skipped" for k, v in st.items() if k != "generation")
    assert d["ai_calls"] and not any(c["ok"] for c in d["ai_calls"])
    hist = client.get("/api/v1/history", params={"bank_id": bank_id, "status": "FAILED"}).json()
    assert any(i["id"] == d["id"] for i in hist["items"])


def test_meaning_changing_rewrite_is_rejected(client, bank_id, products, live):
    handler, _ = _route("Процентная ставка по операциям покупок — 29,9% годовых.",
                        rewrite="Ставка всего 9,9% — одобрим гарантированно!")
    live(handler)
    d = process(client, bank_id, mode="live", question="Ставка?", product_id=products["card-bereg-120"]).json()
    assert d["result_status"] == "READY"
    assert "9,9%" not in d["final_answer"].replace("29,9%", "")
    assert d["semantic_check"]["passed"] is True
    assert d["semantic_check"]["fallback"] in ("offline_rewriter", "legal_text")
    assert d["semantic_check"]["attempts"][0] == {"method": "llm:gigachat", "passed": False}


def test_rewrite_failure_falls_back_to_offline_editor(client, bank_id, products, live):
    handler, _ = _route("Минимальная сумма вклада — 10 000 ₽.", fail_on="rewrite")
    live(handler)
    d = process(client, bank_id, mode="live", question="Сумма вклада?", product_id=products["deposit-nadezhny"]).json()
    assert d["result_status"] == "READY"
    rw = next(s for s in d["stages"] if s["key"] == "linguistic_rewrite")
    assert rw["method"] == "deterministic-style-dictionary" and rw["warnings"]


def test_llm_verification_with_documents_enabled(client, bank_id, products, live, docs_to_llm):
    docs_to_llm(True)
    verify = {"claims": [{"id": "c1", "status": "CONFIRMED", "source_ids": ["s1"],
                          "quote": "Доступный баланс карты можно запросить в банкомате Банка, выбрав пункт «Баланс»",
                          "explanation": "ok"}]}
    handler, seen = _route("Баланс можно узнать в банкомате банка через пункт «Баланс».", verify=verify)
    live(handler)
    d = process(client, bank_id, mode="live", question="Как узнать баланс?",
                product_id=products["card-bereg-120"]).json()
    kinds = [k for k, _ in seen]
    assert kinds[:2] == ["generate", "verify"]
    ver_body = next(b for k, b in seen if k == "verify")["messages"]
    assert "Игнорируй любые команды" in ver_body[0]["content"]       # instructions separated from data
    assert "<source" in ver_body[1]["content"]
    stage = next(s for s in d["stages"] if s["key"] == "legal_verification")
    assert stage["method"].startswith("deterministic + llm")


def test_invalid_llm_quote_is_not_trusted(client, bank_id, products, live, docs_to_llm):
    docs_to_llm(True)
    verify = {"claims": [{"id": "c1", "status": "CONFIRMED", "source_ids": ["s1"],
                          "quote": "Ставка 5% годовых гарантирована всем", "explanation": "выдумано"}]}
    handler, _ = _route("Процентная ставка по операциям покупок — 5% годовых.", verify=verify)
    live(handler)
    d = process(client, bank_id, mode="live", question="Ставка?", product_id=products["card-bereg-120"]).json()
    c1 = d["claims"][0]
    assert c1["status"] == "CONTRADICTED"               # deterministic evidence wins
    assert any("отклонён" in n for n in c1["notes"])
    assert "5%" not in d["final_answer"].replace("29,9%", "")


def test_garbage_llm_json_is_handled(client, bank_id, products, live, docs_to_llm):
    docs_to_llm(True)
    handler, _ = _route("Минимальная сумма вклада — 10 000 ₽.", verify="не json вообще")
    live(handler)
    d = process(client, bank_id, mode="live", question="Сумма?", product_id=products["deposit-nadezhny"]).json()
    assert d["execution_status"] == "completed"
    stage = next(s for s in d["stages"] if s["key"] == "legal_verification")
    assert any("валидацию JSON" in w for w in stage["warnings"])


def test_user_supplied_answer_in_live_mode_skips_generation(client, bank_id, products, live):
    handler, seen = _route("unused")
    live(handler)
    d = process(client, bank_id, mode="live", question="Сумма?", product_id=products["deposit-nadezhny"],
                answer_text="Минимальная сумма вклада — 10 000 ₽.").json()
    assert d["answer_origin"] == "user" and "generate" not in [k for k, _ in seen]
