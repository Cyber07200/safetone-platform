"""Test configuration: an isolated SQLite database migrated with Alembic and
seeded with the demo dataset. No test performs real network calls — live
providers are exercised through httpx.MockTransport."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="safetone-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["STORAGE_DIR"] = str(_TMP / "storage")
os.environ["SAFETONE_MODE"] = "demo"
os.environ["AUTO_SEED_DEMO"] = "true"
for key in ("GIGACHAT_AUTH_KEY", "GIGACHAT_CLIENT_ID", "GIGACHAT_CLIENT_SECRET"):
    os.environ[key] = ""
# Fixed test-only key (not used anywhere else).
os.environ["CHAT_ENCRYPTION_KEY"] = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.main import app, bootstrap  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models import Bank, Product  # noqa: E402
from app.seed.demo_data import DEMO_BANK_SLUG, OTHER_BANK_SLUG, seed_isolation_bank  # noqa: E402

bootstrap()
_s = SessionLocal()
seed_isolation_bank(_s)
_s.close()


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(scope="session")
def bank_id() -> str:
    s = SessionLocal()
    try:
        return s.query(Bank).filter_by(slug=DEMO_BANK_SLUG).one().id
    finally:
        s.close()


@pytest.fixture(scope="session")
def other_bank_id() -> str:
    s = SessionLocal()
    try:
        return s.query(Bank).filter_by(slug=OTHER_BANK_SLUG).one().id
    finally:
        s.close()


@pytest.fixture(scope="session")
def products(bank_id) -> dict[str, str]:
    s = SessionLocal()
    try:
        return {p.code: p.id for p in s.query(Product).filter_by(bank_id=bank_id)}
    finally:
        s.close()


def process(client, bank_id, **kw):
    body = {"bank_id": bank_id, "question": kw.pop("question", "Вопрос клиента"), "mode": "demo",
            "wait": True, **kw}
    return client.post("/api/v1/process", json=body)
