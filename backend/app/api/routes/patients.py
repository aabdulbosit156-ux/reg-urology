import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPrincipal, get_db, require_roles, staff_id_or_none
from app.config import get_settings
from app.models.activity_log import ActivityLog
from app.models.analysis import Analysis
from app.models.appointment import Appointment, AppointmentStatus
from app.models.patient import Patient, PatientSource, PatientStatus
from app.models.staff import Staff, StaffRole
from app.models.status_history import StatusHistory
from app.schemas.analysis import AnalysisOut
from app.schemas.appointment import AppointmentOut
from app.schemas.patient import (
    SEGMENT_STATUSES,
    PatientCreateRequest,
    PatientDetailResponse,
    PatientListResponse,
    PatientOut,
    PatientSegment,
    StatusChangeRequest,
    StatusHistoryOut,
)
from app.services import telegram

router = APIRouter(prefix="/patients", tags=["patients"])
settings = get_settings()

VIEW_ROLES = (StaffRole.dev, StaffRole.director, StaffRole.admin, StaffRole.analyst)
MANAGE_ROLES = (StaffRole.dev, StaffRole.director, StaffRole.admin)

# Mirrors the qabul algoritmi loop in PLAN.md section 5 — enforced here so the workflow
# can't be short-circuited from the admin panel.
VALID_TRANSITIONS: dict[PatientStatus, set[PatientStatus]] = {
    PatientStatus.new: {PatientStatus.scheduled, PatientStatus.unreachable, PatientStatus.advised},
    PatientStatus.unreachable: {
        PatientStatus.scheduled,
        PatientStatus.unreachable,
        PatientStatus.advised,
    },
    PatientStatus.scheduled: {PatientStatus.arrived, PatientStatus.no_show},
    PatientStatus.no_show: {PatientStatus.scheduled, PatientStatus.unreachable},
    PatientStatus.arrived: {PatientStatus.analysis_ordered, PatientStatus.advised},
    PatientStatus.analysis_ordered: {PatientStatus.analysis_ready},
    PatientStatus.analysis_ready: {PatientStatus.advised},
    PatientStatus.advised: {PatientStatus.scheduled},
}

STATUS_NOTIFICATIONS: dict[PatientStatus, str] = {
    PatientStatus.scheduled: "Sizning qabul vaqtingiz belgilandi: {when}.",
    PatientStatus.unreachable: (
        "Siz bilan bog'lanishga urinib ko'rdik, ammo bog'lana olmadik. Tez orada qayta aloqaga chiqamiz."
    ),
    PatientStatus.advised: "Sizga maslahat berildi. Savollaringiz bo'lsa, biz bilan bog'laning.",
    PatientStatus.no_show: "Siz belgilangan qabulga kelmadingiz. Qayta band qilish uchun tez orada bog'lanamiz.",
    PatientStatus.arrived: "Qabulga kelganingiz qayd etildi. Rahmat!",
    PatientStatus.analysis_ordered: (
        "Sizga analiz buyurildi. Namunani suratga olib botga yuboring — mutaxassislarimiz maslahat beradi."
    ),
    PatientStatus.analysis_ready: "Analiz natijalaringiz tayyor.",
}


def _to_out(patient: Patient) -> PatientOut:
    deep_link = None
    if patient.invite_token and settings.bot_username:
        deep_link = f"https://t.me/{settings.bot_username}?start=invite_{patient.invite_token}"
    return PatientOut(
        id=patient.id,
        full_name=patient.full_name,
        phone=patient.phone,
        telegram_user_id=patient.telegram_user_id,
        telegram_username=patient.telegram_username,
        consultation_goal=patient.consultation_goal,
        source=patient.source,
        status=patient.status,
        assigned_staff_id=patient.assigned_staff_id,
        invite_deep_link=deep_link,
        created_at=patient.created_at,
    )


async def _get_patient_or_404(db: AsyncSession, patient_id: uuid.UUID) -> Patient:
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bemor topilmadi")
    return patient


@router.get("", response_model=PatientListResponse)
async def list_patients(
    segment: PatientSegment | None = None,
    search: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    principal: CurrentPrincipal = Depends(require_roles(*VIEW_ROLES)),
) -> PatientListResponse:
    stmt = select(Patient)

    if principal.role == StaffRole.analyst:
        stmt = stmt.where(Patient.status.in_(SEGMENT_STATUSES[PatientSegment.in_progress]))
    elif segment is not None:
        stmt = stmt.where(Patient.status.in_(SEGMENT_STATUSES[segment]))

    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Patient.full_name.ilike(like), Patient.phone.ilike(like)))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Patient.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    patients = result.scalars().all()

    return PatientListResponse(items=[_to_out(p) for p in patients], total=total)


@router.post("", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
async def create_patient(
    payload: PatientCreateRequest,
    db: AsyncSession = Depends(get_db),
    principal: CurrentPrincipal = Depends(require_roles(*MANAGE_ROLES)),
) -> PatientOut:
    patient = Patient(
        full_name=payload.full_name,
        phone=payload.phone,
        consultation_goal=payload.consultation_goal,
        source=PatientSource.manual,
        status=PatientStatus.new,
        invite_token=secrets.token_urlsafe(12),
    )
    db.add(patient)
    await db.flush()

    db.add(
        StatusHistory(
            patient_id=patient.id,
            from_status=None,
            to_status=PatientStatus.new,
            staff_id=staff_id_or_none(principal),
            note="Qo'lda ro'yxatga olindi",
        )
    )
    db.add(
        ActivityLog(
            staff_id=staff_id_or_none(principal),
            action="patient.create",
            entity="patient",
            entity_id=patient.id,
            meta={"source": "manual"},
        )
    )
    await db.commit()
    await db.refresh(patient)
    return _to_out(patient)


@router.get("/{patient_id}", response_model=PatientDetailResponse)
async def get_patient(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: CurrentPrincipal = Depends(require_roles(*VIEW_ROLES)),
) -> PatientDetailResponse:
    patient = await _get_patient_or_404(db, patient_id)

    history_result = await db.execute(
        select(StatusHistory, Staff.full_name)
        .outerjoin(Staff, StatusHistory.staff_id == Staff.id)
        .where(StatusHistory.patient_id == patient_id)
        .order_by(StatusHistory.at)
    )
    history = [
        StatusHistoryOut(
            id=entry.id,
            from_status=entry.from_status,
            to_status=entry.to_status,
            staff_id=entry.staff_id,
            staff_name=staff_name,
            note=entry.note,
            at=entry.at,
        )
        for entry, staff_name in history_result.all()
    ]

    appointments_result = await db.execute(
        select(Appointment)
        .where(Appointment.patient_id == patient_id)
        .order_by(Appointment.start_at.desc())
    )
    appointments = [
        AppointmentOut.model_validate(a) for a in appointments_result.scalars().all()
    ]

    analyses_result = await db.execute(
        select(Analysis).where(Analysis.patient_id == patient_id).order_by(Analysis.created_at.desc())
    )
    analyses = [AnalysisOut.model_validate(a) for a in analyses_result.scalars().all()]

    return PatientDetailResponse(
        **_to_out(patient).model_dump(), history=history, appointments=appointments, analyses=analyses
    )


@router.patch("/{patient_id}/status", response_model=PatientOut)
async def change_status(
    patient_id: uuid.UUID,
    payload: StatusChangeRequest,
    db: AsyncSession = Depends(get_db),
    principal: CurrentPrincipal = Depends(require_roles(*MANAGE_ROLES)),
) -> PatientOut:
    patient = await _get_patient_or_404(db, patient_id)

    allowed = VALID_TRANSITIONS.get(patient.status, set())
    if payload.to_status not in allowed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"'{patient.status.value}' holatidan '{payload.to_status.value}' holatiga o'tib bo'lmaydi",
        )

    notification_when = None
    if payload.to_status == PatientStatus.scheduled:
        if payload.appointment_start_at is None or not payload.appointment_duration_min:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Qabul sanasi va davomiyligi ko'rsatilishi shart"
            )
        await db.execute(
            update(Appointment)
            .where(
                Appointment.patient_id == patient.id,
                Appointment.status == AppointmentStatus.scheduled,
            )
            .values(status=AppointmentStatus.cancelled)
        )
        db.add(
            Appointment(
                patient_id=patient.id,
                staff_id=staff_id_or_none(principal),
                start_at=payload.appointment_start_at,
                duration_min=payload.appointment_duration_min,
            )
        )
        notification_when = payload.appointment_start_at.strftime("%d.%m.%Y %H:%M")

    from_status = patient.status
    patient.status = payload.to_status

    db.add(
        StatusHistory(
            patient_id=patient.id,
            from_status=from_status,
            to_status=payload.to_status,
            staff_id=staff_id_or_none(principal),
            note=payload.note,
        )
    )
    db.add(
        ActivityLog(
            staff_id=staff_id_or_none(principal),
            action="patient.status_change",
            entity="patient",
            entity_id=patient.id,
            meta={"from": from_status.value, "to": payload.to_status.value},
        )
    )
    await db.commit()
    await db.refresh(patient)

    text = STATUS_NOTIFICATIONS.get(payload.to_status)
    if text:
        if notification_when:
            text = text.format(when=notification_when)
        await telegram.send_text(db, patient.telegram_user_id, text)

    return _to_out(patient)


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    principal: CurrentPrincipal = Depends(require_roles(*MANAGE_ROLES)),
) -> None:
    patient = await _get_patient_or_404(db, patient_id)
    db.add(
        ActivityLog(
            staff_id=staff_id_or_none(principal),
            action="patient.delete",
            entity="patient",
            entity_id=patient.id,
            meta={"full_name": patient.full_name},
        )
    )
    await db.delete(patient)
    await db.commit()
