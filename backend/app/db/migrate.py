"""Programmatic Alembic upgrade (used on startup and in tests)."""
from __future__ import annotations

from alembic import command
from alembic.config import Config

from app.core.config import BACKEND_DIR
from app.db import session


def upgrade_to_head() -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", str(session.engine.url.render_as_string(hide_password=False)))
    command.upgrade(cfg, "head")
