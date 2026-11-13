"""SafeTone API — FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager


from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.routes import chat, documents, platform, process
from app.core.config import BACKEND_DIR, get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.db.migrate import upgrade_to_head
from app.db.session import SessionLocal

log = logging.getLogger("safetone")
FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"
MAX_BODY_BYTES = 12 * 1024 * 1024


def bootstrap() -> None:
    """Apply migrations, seed demo data, apply retention policy."""
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    upgrade_to_head()
    db = SessionLocal()
    try:
        if settings.auto_seed_demo:
            from app.seed.demo_data import retire_old_demo_banks, seed_demo
            retire_old_demo_banks(db)
            seed_demo(db)
        if settings.seed_laws:
            from app.seed.laws import seed_laws
            seed_laws(db)
        from app.models import Bank
        from app.services.knowledge.retrieval import warm
        for bank in db.query(Bank).all():
            warm(db, bank.id)
        from app.repositories.store import fail_interrupted_runs, purge_expired_runs
        interrupted = fail_interrupted_runs(db)
        if interrupted:
            log.warning("Marked %s interrupted runs as FAILED", interrupted)
        removed = purge_expired_runs(db)
        if removed:
            log.info("Retention: removed %s expired runs", removed)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    bootstrap()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="SafeTone API",
        version=__version__,
        description="Юридическая проверка и лингвистическое улучшение ответов AI для банковских коммуникаций. "
                    "Все ответы об ошибках имеют формат {\"error\": {\"code\", \"message\", \"details\"}}.",
        lifespan=lifespan,
    )
    install_error_handlers(app)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=False,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type"])

    @app.middleware("http")
    async def _limits_and_headers(request: Request, call_next):
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
            return JSONResponse(status_code=413, content={"error": {
                "code": "PAYLOAD_TOO_LARGE", "message": "Слишком большой запрос", "details": None}})
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    app.include_router(platform.router)
    app.include_router(process.router)
    app.include_router(documents.router)
    app.include_router(chat.router)

    # Optional: serve the built frontend from the same process (single-command demo).
    if FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def _spa(path: str):
            if path.startswith("api/"):
                return JSONResponse(status_code=404, content={"error": {"code": "NOT_FOUND",
                                                                        "message": "Not found", "details": None}})
            candidate = (FRONTEND_DIST / path).resolve()
            if path and FRONTEND_DIST.resolve() in candidate.parents and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")
    return app


app = create_app()

