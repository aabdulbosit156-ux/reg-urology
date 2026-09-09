import asyncio
import logging

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import analysis_upload, menu, registration, start
from app.bot.instance import create_bot


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    bot = await create_bot()
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(start.router)
    dp.include_router(registration.router)
    dp.include_router(menu.router)
    dp.include_router(analysis_upload.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
