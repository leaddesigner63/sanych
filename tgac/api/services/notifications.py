"""Telegram notification helpers for TGAC."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from ..models.core import User
from ..utils.settings import get_settings

try:  # pragma: no cover - aiogram is an optional runtime dependency
    from aiogram import Bot
except Exception:  # pragma: no cover - fallback when aiogram is unavailable
    Bot = None  # type: ignore[assignment]


@dataclass(slots=True)
class NotificationResult:
    """Represents the outcome of a notification dispatch."""

    user_id: int
    chat_id: int
    message: str


class NotificationServiceError(Exception):
    """Base class for notification related errors."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class UserNotFound(NotificationServiceError):
    """Raised when the specified user cannot be located."""


class UserChatNotLinked(NotificationServiceError):
    """Raised when a user has no Telegram chat bound."""


class NotificationConfigurationError(NotificationServiceError):
    """Raised when notification delivery is not properly configured."""


class NotificationDeliveryError(NotificationServiceError):
    """Raised when a notification could not be delivered."""


class NotificationService:
    """Send operational notifications to TG users via Telegram."""

    def __init__(
        self,
        db: Session,
        sender: Callable[[int, str], None] | None = None,
    ) -> None:
        self.db = db
        self._sender = sender

    def send_to_user(self, user_id: int, message: str) -> NotificationResult:
        """Deliver a notification to the user via Telegram."""

        if not message or not message.strip():
            raise NotificationServiceError("Message must not be empty", status_code=422)

        user = self.db.get(User, user_id)
        if user is None:
            raise UserNotFound(f"User {user_id} not found", status_code=404)

        if user.telegram_id is None:
            raise UserChatNotLinked("User is not linked with Telegram", status_code=409)

        chat_id = int(user.telegram_id)
        payload = message.strip()
        self._dispatch(chat_id, payload)
        return NotificationResult(user_id=user.id, chat_id=chat_id, message=payload)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _dispatch(self, chat_id: int, message: str) -> None:
        sender = self._sender or self._send_via_bot
        try:
            sender(chat_id, message)
        except NotificationServiceError:
            raise
        except Exception as exc:  # pragma: no cover - unexpected failures
            raise NotificationDeliveryError("Failed to deliver notification") from exc

    def _send_via_bot(self, chat_id: int, message: str) -> None:
        settings = get_settings()
        token = settings.telegram_bot_token
        if not token:
            raise NotificationConfigurationError("Telegram bot token is not configured", status_code=503)

        if Bot is None:
            raise NotificationConfigurationError("Telegram bot integration is unavailable", status_code=503)

        bot = Bot(token=token)

        async def _send() -> None:
            try:
                await bot.send_message(chat_id=chat_id, text=message)
            finally:
                await bot.session.close()

        try:
            asyncio.run(_send())
        except RuntimeError:
            # Fallback for environments with a running event loop.
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(_send(), loop)
                future.result()
            else:
                raise
        except Exception as exc:  # pragma: no cover - defensive guard
            raise NotificationDeliveryError("Failed to deliver notification") from exc


__all__ = [
    "NotificationService",
    "NotificationServiceError",
    "NotificationResult",
    "NotificationConfigurationError",
    "NotificationDeliveryError",
    "UserNotFound",
    "UserChatNotLinked",
]
