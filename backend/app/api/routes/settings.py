from datetime import time

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_roles
from app.models.clinic_settings import ClinicSettings
from app.models.staff import StaffRole
from app.schemas.settings import ScheduleSettingsOut, ScheduleSettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])

DEFAULT_WORK_START = time(9, 0)
DEFAULT_WORK_END = time(18, 0)
DEFAULT_SLOT_MINUTES = 30

CALENDAR_ROLES = (StaffRole.dev, StaffRole.director, StaffRole.admin)


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
    dependencies=[Depends(require_roles(StaffRole.dev, StaffRole.director))],
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
