from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models import core  # noqa: F401
from tgac.api.models.base import Base
from tgac.api.models.core import LoginToken, LoginTokenStatus
from tgac.api.services.auth_flow import AuthService
from tgac.api.utils.settings import Settings
from tgac.api.utils.time import utcnow


def setup_module(module):
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


@pytest.fixture
def session(monkeypatch):
    session = TestingSession()

    def _settings_factory():
        return Settings(
            telegram_bot_token="TEST",
            base_url="https://example.com",
            db_url="sqlite:///test",
            session_secret_key="a" * 44,
        )

    monkeypatch.setattr("tgac.api.services.auth_flow.get_settings", _settings_factory)
    try:
        yield session
    finally:
        session.close()


def test_create_login_token(session):
    service = AuthService(session)
    token = service.create_login_token()
    assert token.token


def test_find_or_create_user_links_telegram(session):
    service = AuthService(session)
    user = service.find_or_create_user("admin_username", telegram_id=123456)
    assert user.telegram_id == 123456
    assert user.username == "admin_username"


def test_find_or_create_user_updates_existing_chat(session):
    service = AuthService(session)
    first = service.find_or_create_user("admin_username", telegram_id=111)
    assert first.telegram_id == 111

    updated = service.find_or_create_user("admin_username", telegram_id=222)
    assert updated.id == first.id
    assert updated.telegram_id == 222


def test_cleanup_expired_tokens_removes_stale_entries(session):
    service = AuthService(session)
    now = utcnow()
    stale_time = now - timedelta(minutes=60)

    session.query(LoginToken).delete()
    session.commit()

    session.add_all(
        [
            LoginToken(token="stale-pending", created_at=stale_time),
            LoginToken(
                token="stale-expired",
                status=LoginTokenStatus.EXPIRED,
                created_at=stale_time,
            ),
            LoginToken(token="recent", created_at=now - timedelta(minutes=5)),
            LoginToken(
                token="confirmed",
                status=LoginTokenStatus.CONFIRMED,
                created_at=stale_time,
                confirmed_at=stale_time,
            ),
        ]
    )
    session.commit()

    removed = service.cleanup_expired_tokens()

    assert removed == 2
    remaining = {token.token for token in session.query(LoginToken).all()}
    assert remaining == {"recent", "confirmed"}
