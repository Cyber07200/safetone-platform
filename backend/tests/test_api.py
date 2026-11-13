"""REST API, Demo Mode, history and audit (mandatory scenarios 7, 8, 10)."""
from __future__ import annotations

import time

import pytest

from app.services.demo.scenarios import SCENARIOS
from tests.conftest import process


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok" and r.json()["live_available"] is False


def test_openapi_is_available(client):
    paths = client.get("/openapi.json").json()["paths"]
    for p in ("/api/v1/process", "/api/v1/process/{run_id}", "/api/v1/history", "/api/v1/documents",
              "/api/v1/documents/{doc_id}", "/api/v1/banks", "/api/v1/products", "/api/v1/providers",
              "/api/v1/settings"):
        assert p in paths


def test_catalog(client, bank_id):
    assert any(b["id"] == bank_id for b in client.get("/api/v1/banks").json())
    prods = client.get("/api/v1/products", params={"bank_id": bank_id}).json()
    assert {p["code"] for p in prods} >= {"card-bereg-120", "loan-prostoy", "deposit-nadezhny", "rko-start"}
    assert all(p["is_demo"] for p in prods)
    sc = client.get("/api/v1/scenarios", params={"bank_id": bank_id}).json()
    assert len(sc) >= 8 and all(s["product_id"] for s in sc)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.id)
def test_demo_scenarios_via_api(client, bank_id, scenario):
    r = process(client, bank_id, scenario_id=scenario.id)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["execution_status"] == "completed"
    assert d["result_status"] == scenario.expected_status
    assert all(s["status"] == "completed" for s in d["stages"])
    assert d["final_answer"]


# 8. Demo Mode не выдаёт заранее подготовленный результат за реальную генерацию --------
def test_demo_mode_is_labelled_honestly(client, bank_id):
    d = process(client, bank_id, scenario_id="rate-error").json()
    assert d["mode"] == "demo" and d["answer_origin"] == "scenario"
    assert d["provider"] is None and d["model"] is None
    gen = d["stages"][0]
    assert gen["key"] == "generation" and gen["method"] == "demo_scenario"
    assert "не генерация" in gen["summary"]
    assert any("DEMO MODE" in n for n in d["notices"])
    assert d["ai_calls"] == [] and d["tokens_total"] is None


def test_demo_mode_requires_scenario_or_answer(client, bank_id):
    r = process(client, bank_id, question="Какая ставка?")
    assert r.status_code == 422 and r.json()["error"]["code"] == "DEMO_NEEDS_ANSWER"


def test_demo_mode_checks_user_supplied_answer(client, bank_id, products):
    d = process(client, bank_id, question="Ставка по карте?", product_id=products["card-bereg-120"],
                answer_text="Процентная ставка по операциям покупок — 25% годовых.").json()
    assert d["answer_origin"] == "user" and d["stages"][0]["method"] == "user_provided"
    assert "29,9%" in d["final_answer"]


def test_live_mode_without_keys_is_refused_with_hint(client, bank_id):
    r = process(client, bank_id, question="Какая ставка по карте?", mode="live")
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "LIVE_MODE_UNAVAILABLE" and "Demo Mode" in err["message"]


def test_scenario_in_live_mode_is_rejected(client, bank_id):
    r = process(client, bank_id, scenario_id="safe-balance", mode="live")
    assert r.status_code == 422 and r.json()["error"]["code"] == "SCENARIO_REQUIRES_DEMO"


def test_validation_error_format(client, bank_id):
    r = process(client, bank_id, question="x" * 5000, answer_text="ok ok ok")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR" and r.json()["error"]["details"]


def test_unknown_bank_is_404(client):
    r = process(client, "nope", scenario_id="safe-balance")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_async_processing_with_polling(client, bank_id):
    r = client.post("/api/v1/process", json={"bank_id": bank_id, "question": "q q q", "mode": "demo",
                                             "scenario_id": "plain-language"})
    assert r.status_code == 202
    run_id = r.json()["id"]
    assert r.json()["execution_status"] in ("queued", "running", "completed")
    for _ in range(50):
        d = client.get(f"/api/v1/process/{run_id}", params={"bank_id": bank_id}).json()
        if d["execution_status"] == "completed":
            break
        time.sleep(0.05)
    assert d["execution_status"] == "completed" and d["result_status"] == "READY"


# Аудит ----------------------------------------------------------------------------------
def test_audit_contains_every_section(client, bank_id):
    d = process(client, bank_id, scenario_id="contract-conflict", tone="detailed").json()
    assert d["question"] and d["original_answer"] and d["legal_answer"] and d["final_answer"]
    assert [s["key"] for s in d["stages"]] == ["generation", "claim_extraction", "source_retrieval",
                                                 "legal_verification", "legal_correction", "linguistic_rewrite",
                                                 "semantic_validation", "final_response"]
    claim = next(c for c in d["claims"] if c["status"] == "CONTRADICTED")
    for key in ("text", "status", "risk", "explanation", "evidence", "correction"):
        assert claim[key]
    src = d["sources"][0]
    for key in ("title", "doc_type", "version", "section", "quote", "actuality", "is_demo"):
        assert key in src
    assert d["legal_changes"] and d["legal_changes"][0]["basis"]
    assert d["linguistic"]["tone"] == "detailed" and d["linguistic"]["method"]
    assert d["semantic_check"]["passed"] is True and d["semantic_check"]["checks"]
    assert d["max_risk"] == "HIGH"


# 10. История содержит реальные результаты обработки -------------------------------------
def test_history_contains_real_results_and_filters(client, bank_id):
    created = process(client, bank_id, scenario_id="critical-guarantee").json()
    page = client.get("/api/v1/history", params={"bank_id": bank_id, "limit": 100}).json()
    item = next(i for i in page["items"] if i["id"] == created["id"])
    assert item["result_status"] == "NEEDS_REVIEW" and item["max_risk"] == "CRITICAL"
    stored = client.get(f"/api/v1/process/{created['id']}", params={"bank_id": bank_id}).json()
    assert stored["final_answer"] == created["final_answer"]
    assert stored["claims"] == created["claims"]

    only_review = client.get("/api/v1/history", params={"bank_id": bank_id, "status": "NEEDS_REVIEW"}).json()
    assert only_review["total"] >= 1 and all(i["result_status"] == "NEEDS_REVIEW" for i in only_review["items"])
    search = client.get("/api/v1/history", params={"bank_id": bank_id, "q": "гарантируете"}).json()
    assert any(i["id"] == created["id"] for i in search["items"])


def test_history_is_isolated_between_banks(client, bank_id, other_bank_id):
    created = process(client, bank_id, scenario_id="safe-balance").json()
    other = client.get("/api/v1/history", params={"bank_id": other_bank_id}).json()
    assert all(i["id"] != created["id"] for i in other["items"])
    r = client.get(f"/api/v1/process/{created['id']}", params={"bank_id": other_bank_id})
    assert r.status_code == 404


def test_rerun_creates_new_run(client, bank_id):
    first = process(client, bank_id, scenario_id="fee-error").json()
    r = client.post(f"/api/v1/process/{first['id']}/rerun", params={"bank_id": bank_id})
    assert r.status_code in (200, 202)
    assert r.json()["id"] != first["id"] and r.json()["scenario_id"] == "fee-error"


def test_settings_roundtrip(client, bank_id):
    r = client.put("/api/v1/settings", params={"bank_id": bank_id}, json={"default_tone": "friendly",
                                                                          "quality_preference": "quality"})
    assert r.status_code == 200 and r.json()["bank"]["default_tone"] == "friendly"
    assert client.put("/api/v1/settings", params={"bank_id": bank_id},
                      json={"default_provider": "unknown"}).status_code == 422
    client.put("/api/v1/settings", params={"bank_id": bank_id}, json={"default_tone": "neutral",
                                                                     "quality_preference": "balanced"})


def test_providers_endpoint_reports_honest_status(client):
    d = client.get("/api/v1/providers").json()
    assert d["live_available"] is False
    assert {p["name"] for p in d["providers"]} == {"gigachat"}
    assert all(p["status"] == "not_configured" and p["missing_config"] for p in d["providers"])
    chk = client.post("/api/v1/providers/gigachat/check").json()
    assert chk["ok"] is False and chk["code"] == "PROVIDER_NOT_CONFIGURED"


def test_stats(client, bank_id):
    process(client, bank_id, scenario_id="rate-error")
    s = client.get("/api/v1/stats", params={"bank_id": bank_id}).json()
    assert s["total_runs"] >= 1 and s["documents"] >= 9 and s["documents_needing_attention"] >= 1
    assert s["recent"]
