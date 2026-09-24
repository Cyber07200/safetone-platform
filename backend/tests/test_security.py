"""Secrets handling and configuration hygiene."""
from __future__ import annotations

import logging
import re
from pathlib import Path

from app.core.logging import SecretMaskingFilter, redact

ROOT = Path(__file__).resolve().parents[2]


def test_redact_auth_headers():
    assert "[REDACTED]" in redact("Authorization: Api-Key fake-test-key-not-real-0000000000000000")
    assert "AQVN3T06I" not in redact("key=fake-test-key-not-real-0000000000000000")
    assert "abc.def" not in redact("Bearer abc.def")
    assert "sk-abcdefghijk" not in redact("token sk-abcdefghijklmnop")


def test_log_filter_masks_records(caplog):
    logger = logging.getLogger("safetone.test")
    logger.addFilter(SecretMaskingFilter())
    with caplog.at_level(logging.INFO):
        logger.info("calling with Api-Key %s", "AQVNsupersecretvalue123")
    assert "supersecret" not in caplog.text


def test_env_example_has_no_secret_values():
    text = (ROOT / "backend" / ".env.example").read_text("utf-8")
    for name in ("YANDEX_API_KEY", "YANDEX_IAM_TOKEN", "GIGACHAT_AUTH_KEY", "GIGACHAT_CLIENT_SECRET",
                 "OPENAI_API_KEY"):
        m = re.search(rf"^{name}=(.*)$", text, re.M)
        assert m is not None and m.group(1).strip() == "", name


def test_gitignore_excludes_env_and_data():
    gi = (ROOT / ".gitignore").read_text("utf-8")
    for entry in (".env", "*.db", "storage/"):
        assert entry in gi


def test_no_hardcoded_keys_in_source():
    patterns = [re.compile(r"AQVN[A-Za-z0-9_\-]{20,}"), re.compile(r"-----BEGIN (OPENSSH|RSA) PRIVATE KEY"),
                re.compile(r"b1g[a-z0-9]{17}")]
    offenders = []
    for p in list((ROOT / "backend" / "app").rglob("*.py")) + list((ROOT / "frontend" / "src").rglob("*.ts*")):
        t = p.read_text("utf-8", errors="ignore")
        if any(pat.search(t) for pat in patterns):
            offenders.append(str(p))
    assert offenders == []


def test_security_headers(client):
    r = client.get("/api/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"


def test_oversized_body_rejected(client, bank_id):
    r = client.post("/api/v1/process", content=b"x" * (13 * 1024 * 1024),
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
