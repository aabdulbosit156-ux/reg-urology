import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPrincipal, get_db, require_roles, staff_id_or_none
from app.models.activity_log import ActivityLog
from app.models.appointment import Appointment, AppointmentStatus
from app.models.patient import Patient
from app.models.staff import StaffRole
from app.schemas.appointment import (
    AppointmentPatientSummary,
    AppointmentRescheduleRequest,
    CalendarAppointmentOut,
)
from app.services import telegram

router = APIRouter(prefix="/appointments", tags=["appointments"])

CALENDAR_ROLES = (StaffRole.dev, StaffRole.director, StaffRole.admin)


def _to_calendar_out(appointment: Appointment, patient: Patient) -> CalendarAppointmentOut:
    return CalendarAppointmentOut(
        id=appointment.id,
        patient_id=appointment.patient_id,
        staff_id=appointment.staff_id,
        start_at=appointment.start_at,
        duration_min=appointment.duration_min,
        status=appointment.status,
        room=appointment.room,
        patient=AppointmentPatientSummary.model_validate(patient),
    )


@router.get("", response_model=list[CalendarAppointmentOut])
async def list_appointments(
    start: datetime = Query(...),
    end: datetime = Query(...),
    db: AsyncSession = Depends(get_db),
    _: CurrentPrincipal = Depends(require_roles(*CALENDAR_ROLES)),
) -> list[CalendarAppointmentOut]:
    result = await db.execute(
        select(Appointment, Patient)
        .join(Patient, Appointment.patient_id == Patient.id)
        .where(Appointment.start_at >= start, Appointment.start_at < end)
        .order_by(Appointment.start_at)
    )
    return [_to_calendar_out(appointment, patient) for appointment, patient in result.all()]


@router.patch("/{appointment_id}", response_model=CalendarAppointmentOut)
async def reschedule_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentRescheduleRequest,
    db: AsyncSession = Depends(get_db),
    principal: CurrentPrincipal = Depends(require_roles(*CALENDAR_ROLES)),
) -> CalendarAppointmentOut:
    result = await db.execute(select(Appointment).where(Appointment.id == appointment_id))
    appointment = result.scalar_one_or_none()
    if appointment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Qabul topilmadi")
    if appointment.status != AppointmentStatus.scheduled:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Faqat rejalashtirilgan qabulni ko'chirish mumkin"
        )

    patient_result = await db.execute(select(Patient).where(Patient.id == appointment.patient_id))
    patient = patient_result.scalar_one()

    appointment.start_at = payload.start_at
    db.add(
        ActivityLog(
            staff_id=staff_id_or_none(principal),
            action="appointment.reschedule",
            entity="appointment",
            entity_id=appointment.id,
            meta={"start_at": payload.start_at.isoformat()},
        )
    )
    await db.commit()

    when = payload.start_at.strftime("%d.%m.%Y %H:%M")
    await telegram.send_text(db, patient.telegram_user_id, f"Sizning qabul vaqtingiz o'zgartirildi: {when}.")

    return _to_calendar_out(appointment, patient)
