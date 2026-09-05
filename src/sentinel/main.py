"""FastAPI application entrypoint.

Run locally:  uvicorn sentinel.main:app --reload  (from the src/ dir or with PYTHONPATH=src)
"""

from fastapi import FastAPI

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

    app.include_router(router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "app": settings.app_name}

    return app


app = create_app()
