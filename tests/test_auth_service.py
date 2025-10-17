import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models.base import Base
from tgac.api.models import core  # noqa: F401
from tgac.api.services.auth_flow import AuthService
from tgac.api.utils.settings import Settings


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
