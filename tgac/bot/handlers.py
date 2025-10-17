from __future__ import annotations

from typing import Iterable

from aiogram import F, Router
from aiogram.types import Message

from ..api.deps import SessionLocal, get_engine
from ..api.services.auth_flow import AuthService
from .recommendations import AppRecommendation, filter_official_recommendations

router = Router()


def build_recommendations_text(recommendations: Iterable[AppRecommendation]) -> str:
    """Render a human-friendly message with store-safe recommendations."""

    result = filter_official_recommendations(recommendations)
    lines: list[str] = []

    if result.allowed:
        lines.append("Рекомендуемые приложения из официальных магазинов:")
        for item in result.allowed:
            platform_label = item.normalised_platform().capitalize() or ""
            lines.append(f"• {item.name} ({platform_label}): {item.url}")
    else:
        lines.append("Нет приложений из официальных магазинов для отображения.")

    if result.rejected:
        lines.append("")
        lines.append(
            "⚠️ Некоторые ссылки скрыты, так как не ведут в официальные магазины приложения."
        )

    return "\n".join(lines)


@router.message(F.text.startswith("/start"))
async def start_handler(message: Message) -> None:
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Привет! Отправьте /start <token> из веб-интерфейса.")
        return
    token = parts[1]
    with SessionLocal(bind=get_engine()) as session:
        auth_service = AuthService(session)
        auth_service.confirm_token(token, username=message.from_user.username or "", chat_id=message.chat.id)
    await message.answer("Успешный вход, вернитесь в браузер")


@router.message(F.text == "/help")
async def help_handler(message: Message) -> None:
    await message.answer("Используйте /start <token> для авторизации. Уведомления приходят автоматически.")
