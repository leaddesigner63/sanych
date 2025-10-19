import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models import core  # noqa: F401
from tgac.api.models.base import Base
from tgac.api.models.core import User, UserRole
from tgac.api.services.notifications import (
    NotificationConfigurationError,
    NotificationDeliveryError,
    NotificationService,
    UserChatNotLinked,
    UserNotFound,
)
from tgac.api.utils.settings import Settings


@pytest.fixture
def session(monkeypatch):
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    def _settings_factory():
        return Settings(
            telegram_bot_token="TEST",
            base_url="https://example.com",
            db_url="sqlite:///test",
            session_secret_key="a" * 44,
        )

    monkeypatch.setattr("tgac.api.services.notifications.get_settings", _settings_factory)

    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


def _create_user(session: Session, telegram_id: int | None = None) -> User:
    user = User(username="admin_username", role=UserRole.ADMIN, telegram_id=telegram_id)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_send_to_user_uses_custom_sender(session):
    calls: list[tuple[int, str]] = []

    def _sender(chat_id: int, text: str) -> None:
        calls.append((chat_id, text))

    service = NotificationService(session, sender=_sender)
    user = _create_user(session, telegram_id=123)

    result = service.send_to_user(user.id, " Hello world ")

    assert result.chat_id == 123
    assert result.message == "Hello world"
    assert calls == [(123, "Hello world")]


def test_send_to_user_requires_existing_user(session):
    service = NotificationService(session, sender=lambda *_: None)

    with pytest.raises(UserNotFound):
        service.send_to_user(999, "Test")


def test_send_to_user_requires_telegram_binding(session):
    user = _create_user(session, telegram_id=None)
    service = NotificationService(session, sender=lambda *_: None)

    with pytest.raises(UserChatNotLinked):
        service.send_to_user(user.id, "Test")


def test_send_to_user_wraps_sender_errors(session):
    user = _create_user(session, telegram_id=555)

    def _sender(chat_id: int, text: str) -> None:
        raise RuntimeError("boom")

    service = NotificationService(session, sender=_sender)

    with pytest.raises(NotificationDeliveryError):
        service.send_to_user(user.id, "Test")


def test_send_to_user_requires_bot_token(monkeypatch, session):
    def _settings_factory():
        return Settings(
            telegram_bot_token="",
            base_url="https://example.com",
            db_url="sqlite:///test",
            session_secret_key="a" * 44,
        )

    monkeypatch.setattr("tgac.api.services.notifications.get_settings", _settings_factory)

    service = NotificationService(session)
    user = _create_user(session, telegram_id=42)

    with pytest.raises(NotificationConfigurationError):
        service.send_to_user(user.id, "Test")
