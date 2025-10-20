from __future__ import annotations

from collections.abc import Generator

from fastapi import Cookie, Depends, Header, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models.base import Base
from .models.core import User
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


def get_current_user(
    db: Session = Depends(get_db),
    session_cookie: str | None = Cookie(default=None, alias="tgac_session"),
    user_id_header: int | None = Header(default=None, alias="X-User-Id"),
) -> User:
    """Resolve the active user either from session cookie or request header."""

    user_id: int | None = None

    if session_cookie:
        from .services.auth_flow import AuthService

        auth = AuthService(db)
        payload = auth.read_session(session_cookie)
        user_id = int(payload.get("user_id")) if payload.get("user_id") is not None else None
    elif user_id_header is not None:
        user_id = int(user_id_header)

    if user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=403, detail="User is not permitted")

    return user


__all__ = ["Base", "get_db", "SessionLocal", "get_engine", "get_current_user"]
