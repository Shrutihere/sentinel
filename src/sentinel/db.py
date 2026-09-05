"""Database engine, session factory, and declarative base.

The engine URL comes from settings, so the same code runs on SQLite locally and
Postgres in production. SQLite needs check_same_thread=False because FastAPI may
touch a session from a threadpool worker.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def get_session():
    """FastAPI dependency that yields a session and always closes it."""
    with SessionLocal() as session:
        yield session
