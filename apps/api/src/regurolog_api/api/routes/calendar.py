from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from regurolog_api.api.dependencies import (
    CurrentPrincipal,
    ensure_role,
    get_database,
    get_settings,
    require_csrf,
    require_principal,
)
from regurolog_api.config import Settings
from regurolog_api.contracts import BUSINESS_TIMEZONE, AppointmentStatus, StaffRole
from regurolog_api.database import Database
from regurolog_api.domain.validation import (
    DomainValidationError,
    local_day_bounds_utc,
    render_template,
    validate_intervals,
    validate_weekly_intervals,
)
from regurolog_api.errors import ApiError
from regurolog_api.models import (
    Appointment,
    AppointmentEvent,
    BotChatBinding,
    BotConnection,
    ContactAttempt,
    DayOverride,
    Doctor,
    Inquiry,
    Patient,
    ReceptionSheet,
    ScheduleBlock,
    SettingsVersion,
    WorkScheduleVersion,
)
from regurolog_api.schemas import (
    AppointmentCorrectionRequest,
    AppointmentCreateRequest,
    AppointmentRescheduleRequest,
    AppointmentResponse,
    AppointmentTransitionRequest,
    AvailabilityResponse,
    BookableInquiryResponse,
    CalendarDaySummary,
    CalendarSummaryResponse,
    DayOverrideRequest,
    DoctorResponse,
    DoctorUpsertRequest,
    ScheduleBlockRequest,
    WeeklyScheduleRequest,
    WeeklyScheduleResponse,
)
from regurolog_api.services.audit import add_audit
from regurolog_api.services.calendar import CalendarService, domain_error_to_api
from regurolog_api.services.outbox import enqueue_telegram_message
from regurolog_api.services.templates import bot_messages

router = APIRouter()
DatabaseDependency = Annotated[Database, Depends(get_database)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
PrincipalDependency = Annotated[CurrentPrincipal, Depends(require_principal)]
ALL_STAFF = {StaffRole.DEV, StaffRole.DIRECTOR, StaffRole.ADMIN}
MANAGERS = {StaffRole.DEV, StaffRole.DIRECTOR}


def _appointment_response(
    appointment: Appointment,
    settings: Settings,
    patient: Patient | None = None,
) -> AppointmentResponse:
    outcome_pending = appointment.status == "scheduled" and appointment.start_at + timedelta(
        minutes=settings.no_show_grace_minutes
    ) <= datetime.now(UTC)
    return AppointmentResponse(
        id=appointment.id,
        inquiry_id=appointment.inquiry_id,
        doctor_id=appointment.doctor_id,
        start_at=appointment.start_at,
        end_at=appointment.end_at,
        status=AppointmentStatus(appointment.status),
        version=appointment.version,
        outcome_pending=outcome_pending,
        patient_name=patient.full_name if patient else None,
        patient_phone=patient.phone_e164 if patient else None,
        telegram_user_id=patient.telegram_user_id if patient else None,
    )


async def _queue_patient_notification(
    db_session: AsyncSession,
    appointment: Appointment,
    inquiry: Inquiry,
    *,
    action: str,
    template_key: str,
) -> None:
    patient = await db_session.get(Patient, inquiry.patient_id)
    doctor = await db_session.get(Doctor, appointment.doctor_id)
    if patient is None or doctor is None:
        return
    binding_result = await db_session.execute(
        select(BotChatBinding, BotConnection)
        .join(
            BotConnection,
            (BotConnection.bot_id == BotChatBinding.bot_id) & BotConnection.active.is_(True),
        )
        .where(
            BotChatBinding.telegram_user_id == patient.telegram_user_id,
            BotChatBinding.reachable.is_(True),
        )
        .limit(1)
    )
    binding = binding_result.first()
    if binding is None:
        return
    chat_binding, connection = binding
    messages, _ = await bot_messages(db_session)
    local_start = appointment.start_at.astimezone(BUSINESS_TIMEZONE)
    text = render_template(
        messages[template_key],
        {
            "full_name": patient.full_name,
            "doctor_name": doctor.name,
            "date": local_start.strftime("%d.%m.%Y"),
            "time": local_start.strftime("%H:%M"),
            "clinic_address": doctor.clinic_address or "Manzil sozlanmagan",
        },
    )
    await enqueue_telegram_message(
        db_session,
        idempotency_key=f"appointment:{appointment.id}:{appointment.version}:{action}",
        bot_id=connection.bot_id,
        chat_id=chat_binding.chat_id,
        text=text,
        entity_id=appointment.id,
        kind=f"appointment_{action}",
        version=appointment.version,
    )


async def _queue_reminders(
    db_session: AsyncSession, appointment: Appointment, inquiry: Inquiry
) -> None:
    patient = await db_session.get(Patient, inquiry.patient_id)
    doctor = await db_session.get(Doctor, appointment.doctor_id)
    if patient is None or doctor is None:
        return
    binding = await db_session.execute(
        select(BotChatBinding, BotConnection)
        .join(
            BotConnection,
            (BotConnection.bot_id == BotChatBinding.bot_id) & BotConnection.active.is_(True),
        )
        .where(
            BotChatBinding.telegram_user_id == patient.telegram_user_id,
            BotChatBinding.reachable.is_(True),
        )
        .limit(1)
    )
    row = binding.first()
    if row is None:
        return
    chat_binding, connection = row
    now = datetime.now(UTC)
    policy = await db_session.scalar(
        select(SettingsVersion)
        .where(
            SettingsVersion.namespace == "notifications",
            SettingsVersion.state == "published",
        )
        .order_by(SettingsVersion.version.desc())
        .limit(1)
    )
    policy_payload = policy.payload if policy else {}
    if policy_payload.get("reminders_enabled", True) is False:
        return
    reminder_hours = policy_payload.get("reminder_hours", [24, 2])
    if not isinstance(reminder_hours, list):
        reminder_hours = [24, 2]
    messages, _ = await bot_messages(db_session)
    local_start = appointment.start_at.astimezone(BUSINESS_TIMEZONE)
    reminder_text = render_template(
        messages["reminder"],
        {
            "full_name": patient.full_name,
            "doctor_name": doctor.name,
            "date": local_start.strftime("%d.%m.%Y"),
            "time": local_start.strftime("%H:%M"),
            "clinic_address": doctor.clinic_address or "Manzil sozlanmagan",
        },
    )
    for hours in reminder_hours:
        if not isinstance(hours, int):
            continue
        due_at = appointment.start_at - timedelta(hours=hours)
        if due_at <= now:
            continue
        await enqueue_telegram_message(
            db_session,
            idempotency_key=(
                f"appointment:{appointment.id}:{appointment.version}:reminder:{hours}h"
            ),
            bot_id=connection.bot_id,
            chat_id=chat_binding.chat_id,
            text=reminder_text,
            entity_id=appointment.id,
            kind=f"appointment_reminder_{hours}h",
            version=appointment.version,
            due_at=due_at,
        )


@router.get("/doctors", response_model=list[DoctorResponse])
async def list_doctors(
    current: PrincipalDependency, database: DatabaseDependency
) -> list[DoctorResponse]:
    ensure_role(current, ALL_STAFF)
    async with database.session_factory() as db_session:
        doctors = list((await db_session.scalars(select(Doctor).order_by(Doctor.created_at))).all())
    return [
        DoctorResponse(
            id=doctor.id,
            name=doctor.name,
            clinic_address=doctor.clinic_address or "",
            directions=doctor.directions,
            contact_phone=doctor.contact_phone or "",
            timezone="Asia/Tashkent",
            slot_minutes=doctor.slot_minutes,
            active=doctor.active,
        )
        for doctor in doctors
    ]


@router.put("/doctors/primary", response_model=DoctorResponse)
async def upsert_primary_doctor(
    payload: DoctorUpsertRequest,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> DoctorResponse:
    ensure_role(current, MANAGERS)
    require_csrf(request, settings, current)
    now = datetime.now(UTC)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            doctor = await db_session.scalar(
                select(Doctor).where(Doctor.active.is_(True)).with_for_update()
            )
            if doctor is None:
                doctor = Doctor(
                    name=payload.name.strip(),
                    timezone="Asia/Tashkent",
                    active=True,
                    clinic_address=payload.clinic_address.strip(),
                    directions=payload.directions,
                    contact_phone=payload.contact_phone.strip(),
                    created_at=now,
                    updated_at=now,
                )
                db_session.add(doctor)
                await db_session.flush()
            else:
                doctor.name = payload.name.strip()
                doctor.clinic_address = payload.clinic_address.strip()
                doctor.directions = payload.directions
                doctor.contact_phone = payload.contact_phone.strip()
                doctor.updated_at = now
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action="doctor.updated",
                entity_type="doctor",
                entity_id=doctor.id,
                request_id=request.state.request_id,
                occurred_at=now,
            )
    return DoctorResponse(
        id=doctor.id,
        name=doctor.name,
        clinic_address=doctor.clinic_address or "",
        directions=doctor.directions,
        contact_phone=doctor.contact_phone or "",
        timezone="Asia/Tashkent",
        slot_minutes=doctor.slot_minutes,
        active=doctor.active,
    )


@router.get("/schedule/versions", response_model=list[WeeklyScheduleResponse])
async def list_schedule_versions(
    doctor_id: UUID,
    current: PrincipalDependency,
    database: DatabaseDependency,
) -> list[WeeklyScheduleResponse]:
    ensure_role(current, MANAGERS)
    async with database.session_factory() as db_session:
        versions = list(
            (
                await db_session.scalars(
                    select(WorkScheduleVersion)
                    .where(WorkScheduleVersion.doctor_id == doctor_id)
                    .order_by(WorkScheduleVersion.created_at.desc())
                )
            ).all()
        )
        slot_minutes = int(
            await db_session.scalar(select(Doctor.slot_minutes).where(Doctor.id == doctor_id)) or 15
        )
    return [
        WeeklyScheduleResponse(
            id=item.id,
            doctor_id=item.doctor_id,
            effective_from=item.effective_from,
            weekly_intervals=item.weekly_intervals,
            slot_minutes=slot_minutes,
            created_at=item.created_at,
        )
        for item in versions
    ]


@router.post("/schedule/versions", response_model=WeeklyScheduleResponse, status_code=201)
async def create_schedule_version(
    payload: WeeklyScheduleRequest,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> WeeklyScheduleResponse:
    ensure_role(current, MANAGERS)
    require_csrf(request, settings, current)
    try:
        weekly = validate_weekly_intervals(payload.weekly_intervals)
    except DomainValidationError as error:
        raise domain_error_to_api(error) from error
    service = CalendarService(settings)
    now = datetime.now(UTC)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            doctor = await service.lock_doctor(db_session, payload.doctor_id)
            conflicts = await service.conflicting_appointments_for_weekly(
                db_session, payload.doctor_id, payload.effective_from, weekly
            )
            if conflicts:
                raise ApiError(
                    409,
                    "SCHEDULE_CONFLICT",
                    "Yangi jadval kelajak qabullariga zid",
                )
            doctor.slot_minutes = payload.slot_minutes
            doctor.updated_at = now
            # Upsert the single current schedule for this effective date so the form
            # can be re-saved on the same day without a duplicate-version error.
            version = await db_session.scalar(
                select(WorkScheduleVersion)
                .where(
                    WorkScheduleVersion.doctor_id == payload.doctor_id,
                    WorkScheduleVersion.effective_from == payload.effective_from,
                )
                .with_for_update()
            )
            if version is None:
                version = WorkScheduleVersion(
                    doctor_id=payload.doctor_id,
                    effective_from=payload.effective_from,
                    weekly_intervals=weekly,
                    created_by=current.staff.id if current.staff else None,
                    created_at=now,
                )
                db_session.add(version)
                await db_session.flush()
            else:
                version.weekly_intervals = weekly
                version.created_by = current.staff.id if current.staff else version.created_by
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action="schedule.version_created",
                entity_type="work_schedule_version",
                entity_id=version.id,
                request_id=request.state.request_id,
                occurred_at=now,
            )
    return WeeklyScheduleResponse(
        id=version.id,
        doctor_id=version.doctor_id,
        effective_from=version.effective_from,
        weekly_intervals=version.weekly_intervals,
        slot_minutes=payload.slot_minutes,
        created_at=version.created_at,
    )


@router.put("/schedule/day-overrides/{local_date}", status_code=204)
async def put_day_override(
    local_date: date,
    payload: DayOverrideRequest,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> None:
    ensure_role(current, MANAGERS)
    require_csrf(request, settings, current)
    try:
        intervals = validate_intervals(payload.intervals)
    except DomainValidationError as error:
        raise domain_error_to_api(error) from error
    start, end = local_day_bounds_utc(local_date)
    service = CalendarService(settings)
    now = datetime.now(UTC)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            await service.lock_doctor(db_session, payload.doctor_id)
            appointments = list(
                (
                    await db_session.scalars(
                        select(Appointment).where(
                            Appointment.doctor_id == payload.doctor_id,
                            Appointment.status.in_(["scheduled", "checked_in"]),
                            Appointment.start_at >= start,
                            Appointment.start_at < end,
                        )
                    )
                ).all()
            )
            conflicts = [
                item.id
                for item in appointments
                if payload.closed
                or not service._fits(
                    intervals,
                    item.start_at.astimezone(BUSINESS_TIMEZONE),
                    item.end_at.astimezone(BUSINESS_TIMEZONE),
                )
            ]
            if conflicts:
                raise ApiError(409, "SCHEDULE_CONFLICT", "Istisno mavjud qabullarga zid")
            override = await db_session.scalar(
                select(DayOverride)
                .where(
                    DayOverride.doctor_id == payload.doctor_id,
                    DayOverride.local_date == local_date,
                )
                .with_for_update()
            )
            if override is None:
                override = DayOverride(
                    doctor_id=payload.doctor_id,
                    local_date=local_date,
                    intervals=intervals,
                    closed=payload.closed,
                    reason=payload.reason,
                    created_by=current.staff.id if current.staff else None,
                    created_at=now,
                    updated_at=now,
                )
                db_session.add(override)
            else:
                override.intervals = intervals
                override.closed = payload.closed
                override.reason = payload.reason
                override.updated_at = now
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action="schedule.override_saved",
                entity_type="day_override",
                entity_id=override.id,
                request_id=request.state.request_id,
                occurred_at=now,
            )


@router.post("/schedule/blocks", status_code=201)
async def create_schedule_block(
    payload: ScheduleBlockRequest,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> dict[str, str]:
    ensure_role(current, MANAGERS)
    require_csrf(request, settings, current)
    if payload.start_at.tzinfo is None or payload.end_at.tzinfo is None:
        raise ApiError(422, "TIMEZONE_REQUIRED", "Block vaqti timezone bilan yuborilsin")
    start = payload.start_at.astimezone(UTC)
    end = payload.end_at.astimezone(UTC)
    if end <= start:
        raise ApiError(422, "INVALID_BLOCK", "Block oxiri boshlanishidan keyin bo‘lsin")
    service = CalendarService(settings)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            await service.lock_doctor(db_session, payload.doctor_id)
            conflict = await db_session.scalar(
                select(Appointment.id).where(
                    Appointment.doctor_id == payload.doctor_id,
                    Appointment.status.in_(["scheduled", "checked_in"]),
                    Appointment.start_at < end,
                    Appointment.end_at > start,
                )
            )
            if conflict:
                raise ApiError(409, "SCHEDULE_CONFLICT", "Block mavjud qabulga zid")
            block = ScheduleBlock(
                doctor_id=payload.doctor_id,
                start_at=start,
                end_at=end,
                reason=payload.reason,
                created_by=current.staff.id if current.staff else None,
                created_at=datetime.now(UTC),
            )
            db_session.add(block)
            await db_session.flush()
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action="schedule.block_created",
                entity_type="schedule_block",
                entity_id=block.id,
                request_id=request.state.request_id,
                occurred_at=datetime.now(UTC),
            )
    return {"id": str(block.id)}


@router.get("/calendar/availability", response_model=AvailabilityResponse)
async def availability(
    doctor_id: UUID,
    local_date: date,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> AvailabilityResponse:
    ensure_role(current, ALL_STAFF)
    async with database.session_factory() as db_session:
        configured, slots, _ = await CalendarService(settings).availability(
            db_session, doctor_id, local_date
        )
    return AvailabilityResponse(
        doctor_id=doctor_id, local_date=local_date, configured=configured, slots=slots
    )


@router.get("/calendar/summary", response_model=CalendarSummaryResponse)
async def calendar_summary(
    doctor_id: UUID,
    date_from: date,
    date_to: date,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> CalendarSummaryResponse:
    ensure_role(current, ALL_STAFF)
    if date_to < date_from or (date_to - date_from).days > 62:
        raise ApiError(422, "INVALID_DATE_RANGE", "Kalendar sana oralig‘i noto‘g‘ri")
    service = CalendarService(settings)
    range_start, _ = local_day_bounds_utc(date_from)
    _, range_end = local_day_bounds_utc(date_to)
    async with database.session_factory() as db_session:
        appointments = list(
            (
                await db_session.scalars(
                    select(Appointment).where(
                        Appointment.doctor_id == doctor_id,
                        Appointment.start_at >= range_start,
                        Appointment.start_at < range_end,
                    )
                )
            ).all()
        )
        appointments_by_day: dict[date, list[Appointment]] = {}
        for appointment in appointments:
            local_date = appointment.start_at.astimezone(BUSINESS_TIMEZONE).date()
            appointments_by_day.setdefault(local_date, []).append(appointment)
        days: list[CalendarDaySummary] = []
        cursor = date_from
        while cursor <= date_to:
            configured, slots, _ = await service.availability(db_session, doctor_id, cursor)
            day_appointments = appointments_by_day.get(cursor, [])
            days.append(
                CalendarDaySummary(
                    local_date=cursor,
                    configured=configured,
                    total_slots=len(slots),
                    available_slots=sum(slot.available for slot in slots),
                    blocked_slots=sum(slot.state == "blocked" for slot in slots),
                    scheduled=sum(item.status == "scheduled" for item in day_appointments),
                    checked_in=sum(item.status == "checked_in" for item in day_appointments),
                    completed=sum(item.status == "completed" for item in day_appointments),
                    no_show=sum(item.status == "no_show" for item in day_appointments),
                    cancelled=sum(item.status == "cancelled" for item in day_appointments),
                )
            )
            cursor += timedelta(days=1)
    return CalendarSummaryResponse(
        doctor_id=doctor_id,
        date_from=date_from,
        date_to=date_to,
        days=days,
    )


@router.get("/bookable-inquiries", response_model=list[BookableInquiryResponse])
async def bookable_inquiries(
    current: PrincipalDependency,
    database: DatabaseDependency,
) -> list[BookableInquiryResponse]:
    """Open inquiries that answered but have no active appointment yet."""

    ensure_role(current, ALL_STAFF)
    answered = select(ContactAttempt.inquiry_id).where(ContactAttempt.outcome == "answered")
    placed = select(Appointment.inquiry_id).where(
        Appointment.status.in_(["scheduled", "checked_in"])
    )
    statement = (
        select(Inquiry, Patient)
        .join(Patient, Patient.id == Inquiry.patient_id)
        .where(Inquiry.status == "open")
        .where(Inquiry.id.in_(answered))
        .where(Inquiry.id.not_in(placed))
        .order_by(Inquiry.registered_at)
        .limit(200)
    )
    # An ADMIN can only book inquiries assigned to them, so hide the rest.
    if current.role is StaffRole.ADMIN and current.staff is not None:
        statement = statement.where(Inquiry.assigned_to == current.staff.id)
    async with database.session_factory() as db_session:
        rows = (await db_session.execute(statement)).all()
    return [
        BookableInquiryResponse(
            inquiry_id=inquiry.id,
            patient_name=patient.full_name,
            patient_phone=patient.phone_e164,
            registered_at=inquiry.registered_at,
            reason=inquiry.reason,
        )
        for inquiry, patient in rows
    ]


@router.get("/appointments", response_model=list[AppointmentResponse])
async def list_appointments(
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
    doctor_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[AppointmentResponse]:
    ensure_role(current, ALL_STAFF)
    statement = (
        select(Appointment, Patient)
        .join(Inquiry, Inquiry.id == Appointment.inquiry_id)
        .join(Patient, Patient.id == Inquiry.patient_id)
        .order_by(Appointment.start_at)
        .limit(500)
    )
    if doctor_id:
        statement = statement.where(Appointment.doctor_id == doctor_id)
    if date_from:
        start, _ = local_day_bounds_utc(date_from)
        statement = statement.where(Appointment.start_at >= start)
    if date_to:
        _, end = local_day_bounds_utc(date_to)
        statement = statement.where(Appointment.start_at < end)
    async with database.session_factory() as db_session:
        rows = (await db_session.execute(statement)).all()
    return [_appointment_response(appointment, settings, patient) for appointment, patient in rows]


@router.post("/appointments", response_model=AppointmentResponse, status_code=201)
async def create_appointment(
    payload: AppointmentCreateRequest,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> AppointmentResponse:
    ensure_role(current, ALL_STAFF)
    require_csrf(request, settings, current)
    service = CalendarService(settings)
    try:
        async with database.session_factory() as db_session:
            async with db_session.begin():
                doctor = await service.lock_doctor(db_session, payload.doctor_id)
                inquiry = await db_session.get(Inquiry, payload.inquiry_id, with_for_update=True)
                if inquiry is None or inquiry.status != "open":
                    raise ApiError(404, "OPEN_INQUIRY_NOT_FOUND", "Ochiq murojaat topilmadi")
                if current.role is StaffRole.ADMIN and inquiry.assigned_to != current.staff.id:  # type: ignore[union-attr]
                    raise ApiError(403, "OBJECT_FORBIDDEN", "Murojaat sizga biriktirilmagan")
                answered = await db_session.scalar(
                    select(ContactAttempt.id).where(
                        ContactAttempt.inquiry_id == inquiry.id,
                        ContactAttempt.outcome == "answered",
                    )
                )
                if answered is None:
                    raise ApiError(
                        409, "ANSWER_REQUIRED", "Bron uchun bemor javob bergan bo‘lishi kerak"
                    )
                sheet = await db_session.scalar(
                    select(ReceptionSheet)
                    .where(ReceptionSheet.inquiry_id == inquiry.id)
                    .order_by(ReceptionSheet.local_contact_date.desc())
                    .limit(1)
                )
                if sheet is None:
                    raise ApiError(
                        409, "CONTACT_REQUIRED", "Avval qayta aloqa workflowini bajaring"
                    )
                await service.ensure_slot_available(db_session, payload.doctor_id, payload.start_at)
                start = payload.start_at.astimezone(UTC)
                appointment = Appointment(
                    inquiry_id=inquiry.id,
                    doctor_id=payload.doctor_id,
                    sheet_id=sheet.id,
                    start_at=start,
                    end_at=start + timedelta(minutes=doctor.slot_minutes),
                    status="scheduled",
                    created_by=current.staff.id if current.staff else None,
                    schedule_version=1,
                    version=1,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                db_session.add(appointment)
                await db_session.flush()
                db_session.add(
                    AppointmentEvent(
                        appointment_id=appointment.id,
                        action="created",
                        new_start_at=start,
                        new_status="scheduled",
                        actor_id=current.staff.id if current.staff else None,
                        created_at=datetime.now(UTC),
                    )
                )
                await _queue_patient_notification(
                    db_session,
                    appointment,
                    inquiry,
                    action="confirmation",
                    template_key="appointment_confirmation",
                )
                await _queue_reminders(db_session, appointment, inquiry)
                add_audit(
                    db_session,
                    actor_kind=current.kind,
                    actor_id=current.actor_id,
                    action="appointment.created",
                    entity_type="appointment",
                    entity_id=appointment.id,
                    request_id=request.state.request_id,
                    occurred_at=datetime.now(UTC),
                )
        return _appointment_response(appointment, settings)
    except IntegrityError as error:
        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", "")
        if constraint in {
            "excl_appointments_doctor_overlap",
            "uq_appointments_inquiry_active",
        }:
            raise ApiError(
                409, "SLOT_TAKEN", "Bu vaqt yoki murojaat hozirgina band qilindi"
            ) from error
        raise


@router.post("/appointments/{appointment_id}/reschedule", response_model=AppointmentResponse)
async def reschedule_appointment(
    appointment_id: UUID,
    payload: AppointmentRescheduleRequest,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> AppointmentResponse:
    ensure_role(current, ALL_STAFF)
    require_csrf(request, settings, current)
    service = CalendarService(settings)
    try:
        async with database.session_factory() as db_session:
            async with db_session.begin():
                appointment_preview = await db_session.get(Appointment, appointment_id)
                if appointment_preview is None:
                    raise ApiError(404, "APPOINTMENT_NOT_FOUND", "Qabul topilmadi")
                doctor = await service.lock_doctor(db_session, appointment_preview.doctor_id)
                appointment = await db_session.get(
                    Appointment,
                    appointment_id,
                    with_for_update=True,
                    populate_existing=True,
                )
                if appointment is None:
                    raise ApiError(404, "APPOINTMENT_NOT_FOUND", "Qabul topilmadi")
                inquiry = await db_session.get(Inquiry, appointment.inquiry_id)
                assert inquiry is not None
                if appointment.status != "scheduled":
                    raise ApiError(409, "INVALID_TRANSITION", "Faqat rejalangan qabul ko‘chiriladi")
                if appointment.version != payload.version:
                    raise ApiError(409, "VERSION_CONFLICT", "Qabul yangilanib ulgurgan")
                if current.role is StaffRole.ADMIN and inquiry.assigned_to != current.staff.id:  # type: ignore[union-attr]
                    raise ApiError(403, "OBJECT_FORBIDDEN", "Murojaat sizga biriktirilmagan")
                await service.ensure_slot_available(
                    db_session,
                    appointment.doctor_id,
                    payload.start_at,
                    exclude_appointment_id=appointment.id,
                )
                old_start = appointment.start_at
                start = payload.start_at.astimezone(UTC)
                appointment.start_at = start
                appointment.end_at = start + timedelta(minutes=doctor.slot_minutes)
                appointment.version += 1
                appointment.updated_at = datetime.now(UTC)
                db_session.add(
                    AppointmentEvent(
                        appointment_id=appointment.id,
                        action="rescheduled",
                        old_start_at=old_start,
                        new_start_at=start,
                        old_status="scheduled",
                        new_status="scheduled",
                        reason=payload.reason,
                        actor_id=current.staff.id if current.staff else None,
                        created_at=datetime.now(UTC),
                    )
                )
                await _queue_patient_notification(
                    db_session,
                    appointment,
                    inquiry,
                    action="rescheduled",
                    template_key="rescheduled",
                )
                await _queue_reminders(db_session, appointment, inquiry)
                add_audit(
                    db_session,
                    actor_kind=current.kind,
                    actor_id=current.actor_id,
                    action="appointment.rescheduled",
                    entity_type="appointment",
                    entity_id=appointment.id,
                    request_id=request.state.request_id,
                    occurred_at=datetime.now(UTC),
                    note=payload.reason,
                )
        return _appointment_response(appointment, settings)
    except IntegrityError as error:
        raise ApiError(409, "SLOT_TAKEN", "Bu vaqt hozirgina band qilindi") from error


@router.post("/appointments/{appointment_id}/transition", response_model=AppointmentResponse)
async def transition_appointment(
    appointment_id: UUID,
    payload: AppointmentTransitionRequest,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> AppointmentResponse:
    ensure_role(current, ALL_STAFF)
    require_csrf(request, settings, current)
    allowed = {
        "scheduled": {"checked_in", "cancelled", "no_show"},
        "checked_in": {"completed"},
    }
    now = datetime.now(UTC)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            appointment = await db_session.get(Appointment, appointment_id, with_for_update=True)
            if appointment is None:
                raise ApiError(404, "APPOINTMENT_NOT_FOUND", "Qabul topilmadi")
            inquiry = await db_session.get(Inquiry, appointment.inquiry_id, with_for_update=True)
            assert inquiry is not None
            if appointment.version != payload.version:
                raise ApiError(409, "VERSION_CONFLICT", "Qabul yangilanib ulgurgan")
            if current.role is StaffRole.ADMIN and inquiry.assigned_to != current.staff.id:  # type: ignore[union-attr]
                raise ApiError(403, "OBJECT_FORBIDDEN", "Murojaat sizga biriktirilmagan")
            target = payload.status.value
            if target not in allowed.get(appointment.status, set()):
                raise ApiError(409, "INVALID_TRANSITION", "Bu tashrif holati o‘tishi mumkin emas")
            if (
                target == "no_show"
                and appointment.start_at + timedelta(minutes=settings.no_show_grace_minutes) > now
            ):
                raise ApiError(409, "NO_SHOW_TOO_EARLY", "No-show grace vaqti hali tugamagan")
            old_status = appointment.status
            appointment.status = target
            appointment.version += 1
            appointment.updated_at = now
            if target == "completed":
                inquiry.status = "closed"
                inquiry.close_reason = "attended"
                inquiry.version += 1
                inquiry.updated_at = now
            db_session.add(
                AppointmentEvent(
                    appointment_id=appointment.id,
                    action="transition",
                    old_start_at=appointment.start_at,
                    new_start_at=appointment.start_at,
                    old_status=old_status,
                    new_status=target,
                    reason=payload.reason,
                    actor_id=current.staff.id if current.staff else None,
                    created_at=now,
                )
            )
            if target == "cancelled":
                await _queue_patient_notification(
                    db_session,
                    appointment,
                    inquiry,
                    action="cancelled",
                    template_key="cancelled",
                )
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action="appointment.transitioned",
                entity_type="appointment",
                entity_id=appointment.id,
                request_id=request.state.request_id,
                occurred_at=now,
                changes={"from": old_status, "to": target},
                note=payload.reason,
            )
    return _appointment_response(appointment, settings)


@router.post("/appointments/{appointment_id}/correct", response_model=AppointmentResponse)
async def correct_appointment(
    appointment_id: UUID,
    payload: AppointmentCorrectionRequest,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> AppointmentResponse:
    ensure_role(current, MANAGERS)
    require_csrf(request, settings, current)
    service = CalendarService(settings)
    now = datetime.now(UTC)
    try:
        async with database.session_factory() as db_session:
            async with db_session.begin():
                preview = await db_session.get(Appointment, appointment_id)
                if preview is None:
                    raise ApiError(404, "APPOINTMENT_NOT_FOUND", "Qabul topilmadi")
                await service.lock_doctor(db_session, preview.doctor_id)
                appointment = await db_session.get(
                    Appointment,
                    appointment_id,
                    with_for_update=True,
                    populate_existing=True,
                )
                if appointment is None:
                    raise ApiError(404, "APPOINTMENT_NOT_FOUND", "Qabul topilmadi")
                if appointment.version != payload.version:
                    raise ApiError(409, "VERSION_CONFLICT", "Qabul yangilanib ulgurgan")
                target = payload.status.value
                if target == appointment.status:
                    raise ApiError(409, "NO_CORRECTION", "Holat o‘zgarmadi")
                if target == "scheduled":
                    await service.ensure_slot_available(
                        db_session,
                        appointment.doctor_id,
                        appointment.start_at,
                        exclude_appointment_id=appointment.id,
                    )
                inquiry = await db_session.get(
                    Inquiry, appointment.inquiry_id, with_for_update=True
                )
                assert inquiry is not None
                old_status = appointment.status
                appointment.status = target
                appointment.version += 1
                appointment.updated_at = now
                if target == "completed":
                    inquiry.status = "closed"
                    inquiry.close_reason = "attended"
                elif old_status == "completed":
                    inquiry.status = "open"
                    inquiry.close_reason = None
                inquiry.version += 1
                inquiry.updated_at = now
                db_session.add(
                    AppointmentEvent(
                        appointment_id=appointment.id,
                        action="correction",
                        old_start_at=appointment.start_at,
                        new_start_at=appointment.start_at,
                        old_status=old_status,
                        new_status=target,
                        reason=payload.reason,
                        actor_id=current.staff.id if current.staff else None,
                        created_at=now,
                    )
                )
                add_audit(
                    db_session,
                    actor_kind=current.kind,
                    actor_id=current.actor_id,
                    action="appointment.corrected",
                    entity_type="appointment",
                    entity_id=appointment.id,
                    request_id=request.state.request_id,
                    occurred_at=now,
                    changes={"from": old_status, "to": target},
                    note=payload.reason,
                )
        return _appointment_response(appointment, settings)
    except IntegrityError as error:
        raise ApiError(409, "SLOT_TAKEN", "Tuzatilgan holat boshqa qabulga zid") from error
