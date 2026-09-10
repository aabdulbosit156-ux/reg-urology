"""Direct Telegram Bot API calls from the FastAPI process (outside aiogram's polling loop).

Used to push status-change notifications and to move analysis files between the clinic
and the patient's chat without keeping a permanent copy on our own storage — see
PLAN.md section 9 for the storage strategy.
"""

import logging
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.clinic_settings import ClinicSettings
from app.models.staff import Staff, StaffRole

settings = get_settings()
logger = logging.getLogger(__name__)

# Roles that get a heads-up when a new patient/lead appears.
NEW_PATIENT_NOTIFY_ROLES = (StaffRole.director, StaffRole.admin)


async def resolve_bot_token(db: AsyncSession) -> str | None:
    result = await db.execute(select(ClinicSettings).where(ClinicSettings.id == 1))
    clinic = result.scalar_one_or_none()
    if clinic and clinic.bot_token:
        return clinic.bot_token
    return settings.bot_token or None


async def resolve_bot_username(db: AsyncSession) -> str | None:
    result = await db.execute(select(ClinicSettings).where(ClinicSettings.id == 1))
    clinic = result.scalar_one_or_none()
    if clinic and clinic.bot_username:
        return clinic.bot_username
    return settings.bot_username or None


async def fetch_bot_username(token: str) -> str | None:
    """Calls Telegram's getMe so the clinic never has to type the bot's @username by hand."""
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            response.raise_for_status()
        except httpx.HTTPError:
            return None
    return response.json().get("result", {}).get("username")


async def send_text(
    db: AsyncSession,
    telegram_user_id: int | None,
    text: str,
    reply_markup: dict | None = None,
) -> None:
    if not telegram_user_id:
        return
    token = await resolve_bot_token(db)
    if not token:
        logger.warning("Bot token not configured; skipping notification to %s", telegram_user_id)
        return
    payload: dict = {"chat_id": telegram_user_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            logger.exception("Failed to notify patient %s", telegram_user_id)


def ai_analyze_markup(analysis_id: uuid.UUID) -> dict:
    """Inline keyboard matching the bot's ai_report callback handler (callback_data 'ai_analyze:<id>')."""
    return {
        "inline_keyboard": [
            [{"text": "✨ Analizni tahlil qilish", "callback_data": f"ai_analyze:{analysis_id}"}]
        ]
    }


async def notify_staff_new_patient(db: AsyncSession, full_name: str, phone: str, source: str) -> None:
    """Pings director/admin staff (who are on Telegram) about a newly registered patient."""
    result = await db.execute(
        select(Staff).where(
            Staff.role.in_(NEW_PATIENT_NOTIFY_ROLES),
            Staff.is_active.is_(True),
            Staff.telegram_user_id.is_not(None),
        )
    )
    source_label = "Bot orqali" if source == "bot" else "Qo'lda qo'shildi"
    text = f"🆕 Yangi bemor!\n👤 {full_name}\n📞 {phone}\n📍 {source_label}"
    for staff in result.scalars().all():
        await send_text(db, staff.telegram_user_id, text)


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
