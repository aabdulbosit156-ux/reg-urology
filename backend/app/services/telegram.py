"""Direct Telegram Bot API calls from the FastAPI process (outside aiogram's polling loop).

Used to push status-change notifications and to move analysis files between the clinic
and the patient's chat without keeping a permanent copy on our own storage — see
PLAN.md section 9 for the storage strategy.
"""

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.clinic_settings import ClinicSettings

settings = get_settings()
logger = logging.getLogger(__name__)


async def resolve_bot_token(db: AsyncSession) -> str | None:
    result = await db.execute(select(ClinicSettings).where(ClinicSettings.id == 1))
    clinic = result.scalar_one_or_none()
    if clinic and clinic.bot_token:
        return clinic.bot_token
    return settings.bot_token or None


async def send_text(db: AsyncSession, telegram_user_id: int | None, text: str) -> None:
    if not telegram_user_id:
        return
    token = await resolve_bot_token(db)
    if not token:
        logger.warning("Bot token not configured; skipping notification to %s", telegram_user_id)
        return
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": telegram_user_id, "text": text},
            )
            response.raise_for_status()
        except httpx.HTTPError:
            logger.exception("Failed to notify patient %s", telegram_user_id)


async def send_document(
    db: AsyncSession,
    telegram_user_id: int,
    content: bytes,
    filename: str,
    mime_type: str | None,
    caption: str | None = None,
) -> tuple[str, str] | None:
    token = await resolve_bot_token(db)
    if not token:
        return None

    data = {"chat_id": str(telegram_user_id)}
    if caption:
        data["caption"] = caption

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data=data,
            files={"document": (filename, content, mime_type or "application/octet-stream")},
        )
        response.raise_for_status()

    document = response.json()["result"]["document"]
    return document["file_id"], document["file_unique_id"]


async def notify_web_of_change() -> None:
    """Wakes up the web process's SSE subscribers after the bot process (a separate
    container) writes patients/analyses on its own — see app/api/routes/events.py."""
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            await client.post(
                f"{settings.api_base_url}/api/events/broadcast",
                headers={"X-Bot-Secret": settings.bot_internal_secret},
            )
        except httpx.HTTPError:
            logger.warning("Failed to notify web process of a change")


async def download_file(db: AsyncSession, file_id: str) -> bytes | None:
    token = await resolve_bot_token(db)
    if not token:
        return None

    async with httpx.AsyncClient(timeout=30) as client:
        info = await client.get(
            f"https://api.telegram.org/bot{token}/getFile", params={"file_id": file_id}
        )
        info.raise_for_status()
        file_path = info.json()["result"]["file_path"]
        file_response = await client.get(f"https://api.telegram.org/file/bot{token}/{file_path}")
        file_response.raise_for_status()

    return file_response.content
