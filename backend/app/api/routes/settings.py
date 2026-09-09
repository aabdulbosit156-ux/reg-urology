from datetime import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_roles
from app.config import get_settings
from app.models.clinic_settings import ClinicSettings
from app.models.staff import StaffRole
from app.schemas.settings import (
    AISettingsOut,
    AISettingsUpdate,
    BotSettingsOut,
    BotSettingsUpdate,
    BotTextsOut,
    BotTextsUpdate,
    ClinicProfileOut,
    ClinicProfileUpdate,
    ScheduleSettingsOut,
    ScheduleSettingsUpdate,
)
from app.services.bot_texts import DEFAULT_BOT_TEXTS, resolve_bot_texts
from app.services.telegram import fetch_bot_username, resolve_bot_username

router = APIRouter(prefix="/settings", tags=["settings"])
env_settings = get_settings()

DEFAULT_WORK_START = time(9, 0)
DEFAULT_WORK_END = time(18, 0)
DEFAULT_SLOT_MINUTES = 30

CALENDAR_ROLES = (StaffRole.dev, StaffRole.director, StaffRole.admin)
MANAGE_ROLES = (StaffRole.dev, StaffRole.director)


async def _get_or_create_settings(db: AsyncSession) -> ClinicSettings:
    result = await db.execute(select(ClinicSettings).where(ClinicSettings.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        row = ClinicSettings(
            id=1,
            work_start=DEFAULT_WORK_START,
            work_end=DEFAULT_WORK_END,
            slot_minutes=DEFAULT_SLOT_MINUTES,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


@router.get(
    "/schedule",
    response_model=ScheduleSettingsOut,
    dependencies=[Depends(require_roles(*CALENDAR_ROLES))],
)
async def get_schedule_settings(db: AsyncSession = Depends(get_db)) -> ScheduleSettingsOut:
    row = await _get_or_create_settings(db)
    return ScheduleSettingsOut(
        work_start=row.work_start or DEFAULT_WORK_START,
        work_end=row.work_end or DEFAULT_WORK_END,
        slot_minutes=row.slot_minutes,
    )


@router.patch(
    "/schedule",
    response_model=ScheduleSettingsOut,
    dependencies=[Depends(require_roles(*MANAGE_ROLES))],
)
async def update_schedule_settings(
    payload: ScheduleSettingsUpdate, db: AsyncSession = Depends(get_db)
) -> ScheduleSettingsOut:
    row = await _get_or_create_settings(db)
    row.work_start = payload.work_start
    row.work_end = payload.work_end
    row.slot_minutes = payload.slot_minutes
    await db.commit()
    return ScheduleSettingsOut(
        work_start=payload.work_start, work_end=payload.work_end, slot_minutes=payload.slot_minutes
    )


@router.get(
    "/ai",
    response_model=AISettingsOut,
    dependencies=[Depends(require_roles(*MANAGE_ROLES))],
)
async def get_ai_settings(db: AsyncSession = Depends(get_db)) -> AISettingsOut:
    row = await _get_or_create_settings(db)
    return AISettingsOut(ai_token_configured=bool(row.ai_token))


@router.patch(
    "/ai",
    response_model=AISettingsOut,
    dependencies=[Depends(require_roles(*MANAGE_ROLES))],
)
async def update_ai_settings(
    payload: AISettingsUpdate, db: AsyncSession = Depends(get_db)
) -> AISettingsOut:
    row = await _get_or_create_settings(db)
    row.ai_token = payload.ai_token
    await db.commit()
    return AISettingsOut(ai_token_configured=True)


@router.get(
    "/bot",
    response_model=BotSettingsOut,
    dependencies=[Depends(require_roles(*MANAGE_ROLES))],
)
async def get_bot_settings(db: AsyncSession = Depends(get_db)) -> BotSettingsOut:
    row = await _get_or_create_settings(db)
    return BotSettingsOut(
        bot_token_configured=bool(row.bot_token or env_settings.bot_token),
        bot_username=await resolve_bot_username(db),
    )


@router.patch(
    "/bot",
    response_model=BotSettingsOut,
    dependencies=[Depends(require_roles(*MANAGE_ROLES))],
)
async def update_bot_settings(
    payload: BotSettingsUpdate, db: AsyncSession = Depends(get_db)
) -> BotSettingsOut:
    username = await fetch_bot_username(payload.bot_token)
    if username is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bot tokeni yaroqsiz")

    row = await _get_or_create_settings(db)
    row.bot_token = payload.bot_token
    row.bot_username = username
    await db.commit()
    return BotSettingsOut(bot_token_configured=True, bot_username=username)


@router.get(
    "/bot-texts",
    response_model=BotTextsOut,
    dependencies=[Depends(require_roles(*MANAGE_ROLES))],
)
async def get_bot_texts(db: AsyncSession = Depends(get_db)) -> BotTextsOut:
    return BotTextsOut(texts=await resolve_bot_texts(db))


@router.patch(
    "/bot-texts",
    response_model=BotTextsOut,
    dependencies=[Depends(require_roles(*MANAGE_ROLES))],
)
async def update_bot_texts(payload: BotTextsUpdate, db: AsyncSession = Depends(get_db)) -> BotTextsOut:
    row = await _get_or_create_settings(db)
    unknown_keys = set(payload.texts) - set(DEFAULT_BOT_TEXTS)
    if unknown_keys:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Noma'lum matn kaliti: {', '.join(unknown_keys)}")
    row.bot_texts = {**row.bot_texts, **payload.texts}
    await db.commit()
    return BotTextsOut(texts={**DEFAULT_BOT_TEXTS, **row.bot_texts})


@router.get(
    "/clinic",
    response_model=ClinicProfileOut,
    dependencies=[Depends(require_roles(*CALENDAR_ROLES))],
)
async def get_clinic_profile(db: AsyncSession = Depends(get_db)) -> ClinicProfileOut:
    row = await _get_or_create_settings(db)
    return ClinicProfileOut(
        clinic_name=row.clinic_name,
        clinic_lat=row.clinic_lat,
        clinic_lng=row.clinic_lng,
        clinic_contacts=row.clinic_contacts or {},
    )


@router.patch(
    "/clinic",
    response_model=ClinicProfileOut,
    dependencies=[Depends(require_roles(*MANAGE_ROLES))],
)
async def update_clinic_profile(
    payload: ClinicProfileUpdate, db: AsyncSession = Depends(get_db)
) -> ClinicProfileOut:
    row = await _get_or_create_settings(db)
    row.clinic_name = payload.clinic_name
    row.clinic_lat = payload.clinic_lat
    row.clinic_lng = payload.clinic_lng
    row.clinic_contacts = payload.clinic_contacts
    await db.commit()
    return ClinicProfileOut(
        clinic_name=row.clinic_name,
        clinic_lat=row.clinic_lat,
        clinic_lng=row.clinic_lng,
        clinic_contacts=row.clinic_contacts,
    )
