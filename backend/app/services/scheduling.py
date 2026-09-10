"""Server-side slot conflict checks — the calendar UI hides taken slots, but that's just a
hint; this is the actual enforcement so two staff members can't double-book the same time."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment, AppointmentStatus


async def find_conflicting_appointment(
    db: AsyncSession,
    start_at: datetime,
    duration_min: int,
    *,
    exclude_appointment_id: uuid.UUID | None = None,
    exclude_patient_id: uuid.UUID | None = None,
) -> Appointment | None:
    end_at = start_at + timedelta(minutes=duration_min)
    day_start = start_at.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    stmt = select(Appointment).where(
        Appointment.status == AppointmentStatus.scheduled,
        Appointment.start_at >= day_start,
        Appointment.start_at < day_end,
    )
    if exclude_appointment_id is not None:
        stmt = stmt.where(Appointment.id != exclude_appointment_id)
    if exclude_patient_id is not None:
        stmt = stmt.where(Appointment.patient_id != exclude_patient_id)

    result = await db.execute(stmt)
    for candidate in result.scalars().all():
        candidate_end = candidate.start_at + timedelta(minutes=candidate.duration_min)
        if start_at < candidate_end and candidate.start_at < end_at:
            return candidate
    return None
