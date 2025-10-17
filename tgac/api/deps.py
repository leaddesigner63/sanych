from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models.base import Base
from .utils.settings import get_settings

_engine_instance = None
SessionLocal = sessionmaker(autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def get_engine():
    global _engine_instance
    if _engine_instance is None:
        settings = get_settings()
        _engine_instance = create_engine(settings.db_url, echo=False, pool_pre_ping=True, future=True)
    return _engine_instance


def get_db() -> Generator[Session, None, None]:
    engine = get_engine()
    db = SessionLocal(bind=engine)
    try:
        yield db
    finally:
        db.close()


__all__ = ["Base", "get_db", "SessionLocal", "get_engine"]
