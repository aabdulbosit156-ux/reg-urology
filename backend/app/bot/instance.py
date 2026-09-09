from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.database import AsyncSessionLocal
from app.services.telegram import resolve_bot_token


async def create_bot() -> Bot:
    async with AsyncSessionLocal() as db:
        token = await resolve_bot_token(db)

    if not token:
        raise RuntimeError(
            "Bot token is not configured. Set BOT_TOKEN in .env or clinic_settings.bot_token."
        )
    return Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
