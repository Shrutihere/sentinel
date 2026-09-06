"""FastAPI application entrypoint.

Run locally:  uvicorn sentinel.main:app --reload  (from the src/ dir or with PYTHONPATH=src)
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import models  # noqa: F401  (ensure models are registered on Base before create_all)
from .config import settings
from .db import Base, engine
from .gateway import router


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="Risk-evaluation & approval engine for autonomous AI agents",
        version="0.1.0",
    )

    # M0: create tables on startup. Real migrations (Alembic) come with Postgres later.
    Base.metadata.create_all(bind=engine)

    # M5: allow the React dashboard (dev server) to call the API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "app": settings.app_name}

    # If the built dashboard is present, serve it at "/" (single-origin in prod).
    # Mounted last so API routes (/v1, /health, /docs) always take precedence.
    dist = Path(settings.static_dir)
    if dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="dashboard")

    return app


app = create_app()
