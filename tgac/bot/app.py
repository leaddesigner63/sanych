from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from ..api.utils.settings import get_settings
from .handlers import router

logger = logging.getLogger(__name__)


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(router)
    return dp


async def run_bot() -> None:
    settings = get_settings()
    bot = Bot(token=settings.telegram_bot_token)
    dp = create_dispatcher()
    logger.info("Starting Telegram bot")
    await dp.start_polling(bot)


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_bot())
