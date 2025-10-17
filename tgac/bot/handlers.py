from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

from ..api.deps import SessionLocal, get_engine
from ..api.services.auth_flow import AuthService

router = Router()


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
