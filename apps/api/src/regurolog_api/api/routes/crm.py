from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from regurolog_api.api.dependencies import (
    CurrentPrincipal,
    ensure_role,
    get_database,
    get_settings,
    require_csrf,
    require_principal,
)
from regurolog_api.config import Settings
from regurolog_api.contracts import (
    BUSINESS_TIMEZONE,
    ContactAttemptOutcome,
    StaffRole,
    appointment_status_label,
    close_reason_label,
    contact_outcome_label,
)
from regurolog_api.database import Database
from regurolog_api.domain.validation import mask_phone, normalize_full_name, normalize_uz_phone
from regurolog_api.errors import ApiError
from regurolog_api.models import (
    Appointment,
    AuditEvent,
    ContactAttempt,
    ContactNote,
    Inquiry,
    Patient,
    ReceptionSheet,
    SheetAttempt,
    StaffUser,
)
from regurolog_api.schemas import (
    ContactAttemptFinishRequest,
    ContactAttemptResponse,
    ContactAttemptStartResponse,
    ContactNoteRequest,
    InquiryAssignRequest,
    InquiryCloseRequest,
    InquiryReopenRequest,
    InquiryResponse,
    PatientDetailResponse,
    PatientListItem,
    PatientListResponse,
    PatientUpdateRequest,
    ReceptionSheetResponse,
    TimelineItem,
)
from regurolog_api.services.audit import add_audit

router = APIRouter()
DatabaseDependency = Annotated[Database, Depends(get_database)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
PrincipalDependency = Annotated[CurrentPrincipal, Depends(require_principal)]
ALL_STAFF = {StaffRole.DEV, StaffRole.DIRECTOR, StaffRole.ADMIN}
MANAGERS = {StaffRole.DEV, StaffRole.DIRECTOR}


def _actor_key(current: CurrentPrincipal) -> str:
    return f"{current.kind}:{current.actor_id or 'root'}"


def _inquiry_response(inquiry: Inquiry) -> InquiryResponse:
    return InquiryResponse(
        id=inquiry.id,
        patient_id=inquiry.patient_id,
        doctor_id=inquiry.doctor_id,
        status=inquiry.status,
        close_reason=inquiry.close_reason,
        assigned_to=inquiry.assigned_to,
        reason=inquiry.reason,
        registered_at=inquiry.registered_at,
        next_followup_at=inquiry.next_followup_at,
        version=inquiry.version,
    )


@router.get("/patients", response_model=PatientListResponse)
async def list_patients(
    current: PrincipalDependency,
    database: DatabaseDependency,
    search: str | None = Query(default=None, max_length=120),
    status: str | None = Query(default=None, pattern="^(open|closed)$"),
    close_reason: str | None = Query(default=None, max_length=32),
    assigned_to: UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> PatientListResponse:
    ensure_role(current, ALL_STAFF)
    latest_inquiry = select(
        Inquiry,
        func.row_number()
        .over(partition_by=Inquiry.patient_id, order_by=Inquiry.registered_at.desc())
        .label("row_number"),
    ).subquery()
    inquiry = latest_inquiry.alias("latest_inquiry")
    statement = (
        select(
            Patient,
            inquiry.c.id.label("inquiry_id"),
            inquiry.c.status.label("inquiry_status"),
            inquiry.c.close_reason.label("close_reason"),
            StaffUser.full_name.label("assigned_name"),
            func.bool_or(ContactAttempt.outcome == "answered").label("ever_answered"),
            func.max(Appointment.status)
            .filter(Appointment.status.in_(["scheduled", "checked_in"]))
            .label("appointment_status"),
        )
        .outerjoin(inquiry, (inquiry.c.patient_id == Patient.id) & (inquiry.c.row_number == 1))
        .outerjoin(StaffUser, StaffUser.id == inquiry.c.assigned_to)
        .outerjoin(ContactAttempt, ContactAttempt.inquiry_id == inquiry.c.id)
        .outerjoin(Appointment, Appointment.inquiry_id == inquiry.c.id)
        .group_by(
            Patient.id, inquiry.c.id, inquiry.c.status, inquiry.c.close_reason, StaffUser.full_name
        )
    )
    count_statement = select(func.count(Patient.id))
    filters = []
    if search:
        cleaned = search.strip().replace("%", r"\%").replace("_", r"\_")
        filters.append(
            or_(
                Patient.full_name.ilike(f"%{cleaned}%", escape="\\"),
                Patient.phone_e164.ilike(f"%{cleaned}%", escape="\\"),
            )
        )
    if status:
        filters.append(inquiry.c.status == status)
    if close_reason:
        filters.append(inquiry.c.close_reason == close_reason)
    if assigned_to:
        filters.append(inquiry.c.assigned_to == assigned_to)
    statement = statement.where(*filters)
    count_statement = count_statement.outerjoin(
        inquiry, (inquiry.c.patient_id == Patient.id) & (inquiry.c.row_number == 1)
    ).where(*filters)
    statement = (
        statement.order_by(Patient.first_registered_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    async with database.session_factory() as db_session:
        rows = (await db_session.execute(statement)).all()
        total = int((await db_session.scalar(count_statement)) or 0)
    return PatientListResponse(
        items=[
            PatientListItem(
                id=patient.id,
                full_name=patient.full_name,
                phone_masked=mask_phone(patient.phone_e164),
                possible_duplicate=patient.possible_duplicate,
                first_registered_at=patient.first_registered_at,
                inquiry_id=inquiry_id,
                inquiry_status=inquiry_status,
                close_reason=close_reason_value,
                assigned_to_name=assigned_name,
                ever_answered=bool(ever_answered),
                appointment_status=appointment_status,
            )
            for (
                patient,
                inquiry_id,
                inquiry_status,
                close_reason_value,
                assigned_name,
                ever_answered,
                appointment_status,
            ) in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/patients/{patient_id}", response_model=PatientDetailResponse)
async def patient_detail(
    patient_id: UUID,
    request: Request,
    current: PrincipalDependency,
    database: DatabaseDependency,
) -> PatientDetailResponse:
    ensure_role(current, ALL_STAFF)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            patient = await db_session.get(Patient, patient_id)
            if patient is None:
                raise ApiError(404, "PATIENT_NOT_FOUND", "Bemor topilmadi")
            inquiry = await db_session.scalar(
                select(Inquiry)
                .where(Inquiry.patient_id == patient.id)
                .order_by(Inquiry.registered_at.desc())
                .limit(1)
            )
            ever_answered = bool(
                inquiry
                and await db_session.scalar(
                    select(ContactAttempt.id).where(
                        ContactAttempt.inquiry_id == inquiry.id,
                        ContactAttempt.outcome == "answered",
                    )
                )
            )
            active_appointment_status = (
                await db_session.scalar(
                    select(Appointment.status)
                    .where(
                        Appointment.inquiry_id == inquiry.id,
                        Appointment.status.in_(["scheduled", "checked_in"]),
                    )
                    .limit(1)
                )
                if inquiry
                else None
            )
            timeline: list[TimelineItem] = []
            inquiry_ids = list(
                (
                    await db_session.scalars(
                        select(Inquiry.id).where(Inquiry.patient_id == patient.id)
                    )
                ).all()
            )
            if inquiry_ids:
                attempts = list(
                    (
                        await db_session.scalars(
                            select(ContactAttempt)
                            .where(ContactAttempt.inquiry_id.in_(inquiry_ids))
                            .order_by(ContactAttempt.started_at.desc())
                        )
                    ).all()
                )
                appointments = list(
                    (
                        await db_session.scalars(
                            select(Appointment)
                            .where(Appointment.inquiry_id.in_(inquiry_ids))
                            .order_by(Appointment.start_at.desc())
                        )
                    ).all()
                )
                timeline.extend(
                    TimelineItem(
                        kind="contact",
                        title=f"Qayta aloqa: {contact_outcome_label(attempt.outcome)}",
                        occurred_at=attempt.started_at,
                    )
                    for attempt in attempts
                )
                timeline.extend(
                    TimelineItem(
                        kind="appointment",
                        title=f"Qabul: {appointment_status_label(appointment.status)}",
                        occurred_at=appointment.start_at,
                    )
                    for appointment in appointments
                )
                status_events = list(
                    (
                        await db_session.scalars(
                            select(AuditEvent)
                            .where(
                                AuditEvent.entity_type == "inquiry",
                                AuditEvent.entity_id.in_([str(i) for i in inquiry_ids]),
                                AuditEvent.action.in_(["inquiry.closed", "inquiry.reopened"]),
                            )
                            .order_by(AuditEvent.occurred_at.desc())
                        )
                    ).all()
                )
                for event in status_events:
                    if event.action == "inquiry.closed":
                        reason_code = str(event.changes.get("close_reason") or "")
                        title = f"Status: yopildi — {close_reason_label(reason_code)}"
                    else:
                        title = "Status: qayta ochildi"
                    timeline.append(
                        TimelineItem(
                            kind="status",
                            title=title,
                            occurred_at=event.occurred_at,
                            detail=event.note,
                        )
                    )
            timeline.append(
                TimelineItem(
                    kind="registration",
                    title="Bemor ro‘yxatdan o‘tdi",
                    occurred_at=patient.first_registered_at,
                )
            )
            timeline.sort(key=lambda item: item.occurred_at, reverse=True)
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action="patient.contact_viewed",
                entity_type="patient",
                entity_id=patient.id,
                request_id=request.state.request_id,
                occurred_at=datetime.now(UTC),
            )
        return PatientDetailResponse(
            id=patient.id,
            full_name=patient.full_name,
            phone_masked=mask_phone(patient.phone_e164),
            phone_e164=patient.phone_e164,
            telegram_user_id=patient.telegram_user_id,
            possible_duplicate=patient.possible_duplicate,
            ever_answered=ever_answered,
            inquiry_id=inquiry.id if inquiry else None,
            inquiry_status=inquiry.status if inquiry else None,
            close_reason=inquiry.close_reason if inquiry else None,
            appointment_status=active_appointment_status,
            reason=inquiry.reason if inquiry else None,
            assigned_to=inquiry.assigned_to if inquiry else None,
            next_followup_at=inquiry.next_followup_at if inquiry else None,
            version=inquiry.version if inquiry else None,
            timeline=timeline,
        )


@router.patch("/patients/{patient_id}", response_model=PatientDetailResponse)
async def update_patient(
    patient_id: UUID,
    payload: PatientUpdateRequest,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> PatientDetailResponse:
    ensure_role(current, ALL_STAFF)
    require_csrf(request, settings, current)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            patient = await db_session.get(Patient, patient_id, with_for_update=True)
            if patient is None:
                raise ApiError(404, "PATIENT_NOT_FOUND", "Bemor topilmadi")
            inquiry = await db_session.scalar(
                select(Inquiry)
                .where(Inquiry.patient_id == patient.id)
                .order_by(Inquiry.registered_at.desc())
                .with_for_update()
                .limit(1)
            )
            if inquiry is None or inquiry.version != payload.version:
                raise ApiError(
                    409, "VERSION_CONFLICT", "Ma’lumot boshqa foydalanuvchi tomonidan yangilangan"
                )
            changed: dict[str, object] = {}
            if payload.full_name is not None:
                patient.full_name = normalize_full_name(payload.full_name)
                changed["full_name"] = "updated"
            if payload.phone is not None:
                patient.phone_e164 = normalize_uz_phone(payload.phone)
                patient.phone_source = "staff"
                patient.phone_verified = False
                changed["phone"] = "updated"
                duplicates = list(
                    (
                        await db_session.scalars(
                            select(Patient).where(
                                Patient.phone_e164 == patient.phone_e164,
                                Patient.id != patient.id,
                            )
                        )
                    ).all()
                )
                patient.possible_duplicate = bool(duplicates)
                for duplicate in duplicates:
                    duplicate.possible_duplicate = True
                    duplicate.updated_at = datetime.now(UTC)
            patient.updated_at = datetime.now(UTC)
            inquiry.version += 1
            inquiry.updated_at = datetime.now(UTC)
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action="patient.updated",
                entity_type="patient",
                entity_id=patient.id,
                request_id=request.state.request_id,
                occurred_at=datetime.now(UTC),
                changes=changed,
            )
            ever_answered = bool(
                await db_session.scalar(
                    select(ContactAttempt.id).where(
                        ContactAttempt.inquiry_id == inquiry.id,
                        ContactAttempt.outcome == "answered",
                    )
                )
            )
        return PatientDetailResponse(
            id=patient.id,
            full_name=patient.full_name,
            phone_masked=mask_phone(patient.phone_e164),
            phone_e164=patient.phone_e164,
            telegram_user_id=patient.telegram_user_id,
            possible_duplicate=patient.possible_duplicate,
            ever_answered=ever_answered,
            inquiry_id=inquiry.id,
            inquiry_status=inquiry.status,
            close_reason=inquiry.close_reason,
            reason=inquiry.reason,
            assigned_to=inquiry.assigned_to,
            next_followup_at=inquiry.next_followup_at,
            version=inquiry.version,
            timeline=[],
        )


@router.get("/inquiries", response_model=list[InquiryResponse])
async def list_inquiries(
    current: PrincipalDependency,
    database: DatabaseDependency,
    status: str | None = Query(default="open", pattern="^(open|closed)$"),
) -> list[InquiryResponse]:
    ensure_role(current, ALL_STAFF)
    statement = select(Inquiry).order_by(Inquiry.registered_at.desc()).limit(100)
    if status:
        statement = statement.where(Inquiry.status == status)
    async with database.session_factory() as db_session:
        inquiries = list((await db_session.scalars(statement)).all())
    return [_inquiry_response(inquiry) for inquiry in inquiries]


@router.get("/inquiries/{inquiry_id}", response_model=InquiryResponse)
async def inquiry_detail(
    inquiry_id: UUID, current: PrincipalDependency, database: DatabaseDependency
) -> InquiryResponse:
    ensure_role(current, ALL_STAFF)
    async with database.session_factory() as db_session:
        inquiry = await db_session.get(Inquiry, inquiry_id)
    if inquiry is None:
        raise ApiError(404, "INQUIRY_NOT_FOUND", "Murojaat topilmadi")
    return _inquiry_response(inquiry)


@router.post("/inquiries/{inquiry_id}/assign", response_model=InquiryResponse)
async def assign_inquiry(
    inquiry_id: UUID,
    payload: InquiryAssignRequest,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> InquiryResponse:
    ensure_role(current, MANAGERS)
    require_csrf(request, settings, current)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            inquiry = await db_session.get(Inquiry, inquiry_id, with_for_update=True)
            if inquiry is None:
                raise ApiError(404, "INQUIRY_NOT_FOUND", "Murojaat topilmadi")
            if inquiry.version != payload.version:
                raise ApiError(409, "VERSION_CONFLICT", "Murojaat yangilanib ulgurgan")
            if payload.staff_id:
                staff = await db_session.get(StaffUser, payload.staff_id)
                if staff is None or staff.state != "active":
                    raise ApiError(422, "STAFF_NOT_ACTIVE", "Faol xodim tanlang")
            inquiry.assigned_to = payload.staff_id
            inquiry.version += 1
            inquiry.updated_at = datetime.now(UTC)
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action="inquiry.assigned",
                entity_type="inquiry",
                entity_id=inquiry.id,
                request_id=request.state.request_id,
                occurred_at=datetime.now(UTC),
                changes={"assigned_to": str(payload.staff_id) if payload.staff_id else None},
                note=payload.reason,
            )
    return _inquiry_response(inquiry)


@router.post("/inquiries/{inquiry_id}/close", response_model=InquiryResponse)
async def close_inquiry(
    inquiry_id: UUID,
    payload: InquiryCloseRequest,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> InquiryResponse:
    ensure_role(current, ALL_STAFF)
    require_csrf(request, settings, current)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            inquiry = await db_session.get(Inquiry, inquiry_id, with_for_update=True)
            if inquiry is None:
                raise ApiError(404, "INQUIRY_NOT_FOUND", "Murojaat topilmadi")
            if inquiry.version != payload.version:
                raise ApiError(409, "VERSION_CONFLICT", "Murojaat yangilanib ulgurgan")
            # Linear pipeline: an inquiry with a live appointment cannot be closed
            # until that appointment is resolved (completed / cancelled / no-show),
            # otherwise a closed inquiry would keep an active slot booked.
            active_appointment = await db_session.scalar(
                select(Appointment.id).where(
                    Appointment.inquiry_id == inquiry.id,
                    Appointment.status.in_(["scheduled", "checked_in"]),
                )
            )
            if active_appointment is not None:
                raise ApiError(
                    409,
                    "ACTIVE_APPOINTMENT_EXISTS",
                    "Avval kalendardan faol qabulni bekor qiling yoki yakunlang",
                )
            if current.role is StaffRole.ADMIN and inquiry.assigned_to != current.staff.id:  # type: ignore[union-attr]
                raise ApiError(
                    403, "OBJECT_FORBIDDEN", "Faqat biriktirilgan murojaatni yopishingiz mumkin"
                )
            if current.role is StaffRole.ADMIN and payload.close_reason == "unreachable":
                unanswered = int(
                    (
                        await db_session.scalar(
                            select(func.count(ContactAttempt.id)).where(
                                ContactAttempt.inquiry_id == inquiry.id,
                                ContactAttempt.outcome.in_(["no_answer", "busy", "unreachable"]),
                            )
                        )
                    )
                    or 0
                )
                if unanswered < 3:
                    raise ApiError(
                        409,
                        "UNREACHABLE_REQUIRES_ATTEMPTS",
                        "Aloqa qilib bo‘lmadi deb yopish uchun kamida 3 urinish kerak",
                    )
            inquiry.status = "closed"
            inquiry.close_reason = payload.close_reason
            inquiry.version += 1
            inquiry.updated_at = datetime.now(UTC)
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action="inquiry.closed",
                entity_type="inquiry",
                entity_id=inquiry.id,
                request_id=request.state.request_id,
                occurred_at=datetime.now(UTC),
                changes={"close_reason": payload.close_reason},
                note=payload.reason,
            )
    return _inquiry_response(inquiry)


@router.post("/inquiries/{inquiry_id}/reopen", response_model=InquiryResponse)
async def reopen_inquiry(
    inquiry_id: UUID,
    payload: InquiryReopenRequest,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> InquiryResponse:
    ensure_role(current, MANAGERS)
    require_csrf(request, settings, current)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            inquiry = await db_session.get(Inquiry, inquiry_id, with_for_update=True)
            if inquiry is None:
                raise ApiError(404, "INQUIRY_NOT_FOUND", "Murojaat topilmadi")
            if inquiry.version != payload.version:
                raise ApiError(409, "VERSION_CONFLICT", "Murojaat yangilanib ulgurgan")
            if inquiry.status != "closed":
                raise ApiError(409, "INQUIRY_ALREADY_OPEN", "Murojaat allaqachon ochiq")
            inquiry.status = "open"
            inquiry.close_reason = None
            inquiry.version += 1
            inquiry.updated_at = datetime.now(UTC)
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action="inquiry.reopened",
                entity_type="inquiry",
                entity_id=inquiry.id,
                request_id=request.state.request_id,
                occurred_at=datetime.now(UTC),
                note=payload.reason,
            )
    return _inquiry_response(inquiry)


@router.post("/inquiries/{inquiry_id}/release", response_model=InquiryResponse)
async def release_inquiry(
    inquiry_id: UUID,
    payload: InquiryReopenRequest,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> InquiryResponse:
    ensure_role(current, ALL_STAFF)
    require_csrf(request, settings, current)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            inquiry = await db_session.get(Inquiry, inquiry_id, with_for_update=True)
            if inquiry is None:
                raise ApiError(404, "INQUIRY_NOT_FOUND", "Murojaat topilmadi")
            if inquiry.version != payload.version:
                raise ApiError(409, "VERSION_CONFLICT", "Murojaat yangilanib ulgurgan")
            if current.role is StaffRole.ADMIN and inquiry.assigned_to != current.staff.id:  # type: ignore[union-attr]
                raise ApiError(403, "OBJECT_FORBIDDEN", "Murojaat sizga biriktirilmagan")
            inquiry.assigned_to = None
            inquiry.version += 1
            inquiry.updated_at = datetime.now(UTC)
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action="inquiry.released",
                entity_type="inquiry",
                entity_id=inquiry.id,
                request_id=request.state.request_id,
                occurred_at=datetime.now(UTC),
                note=payload.reason,
            )
    return _inquiry_response(inquiry)


@router.post(
    "/inquiries/{inquiry_id}/contact-attempts",
    response_model=ContactAttemptStartResponse,
    status_code=201,
)
async def start_contact_attempt(
    inquiry_id: UUID,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ContactAttemptStartResponse:
    ensure_role(current, ALL_STAFF)
    require_csrf(request, settings, current)
    if not idempotency_key or len(idempotency_key) > 80:
        raise ApiError(422, "IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key yuboring")
    now = datetime.now(UTC)
    actor_key = _actor_key(current)
    try:
        async with database.session_factory() as db_session:
            async with db_session.begin():
                inquiry = await db_session.get(Inquiry, inquiry_id, with_for_update=True)
                if inquiry is None or inquiry.status != "open":
                    raise ApiError(404, "OPEN_INQUIRY_NOT_FOUND", "Ochiq murojaat topilmadi")
                existing = await db_session.scalar(
                    select(ContactAttempt).where(
                        ContactAttempt.actor_key == actor_key,
                        ContactAttempt.idempotency_key == idempotency_key,
                    )
                )
                if existing:
                    sheet = await db_session.scalar(
                        select(ReceptionSheet)
                        .join(SheetAttempt, SheetAttempt.sheet_id == ReceptionSheet.id)
                        .where(SheetAttempt.attempt_id == existing.id)
                    )
                    if sheet is None:
                        raise ApiError(409, "ATTEMPT_STATE_CONFLICT", "Urinish varaqasi topilmadi")
                    patient = await db_session.get(Patient, inquiry.patient_id)
                    assert patient is not None
                    return ContactAttemptStartResponse(
                        id=existing.id,
                        inquiry_id=inquiry.id,
                        phone_e164=patient.phone_e164,
                        outcome=ContactAttemptOutcome(existing.outcome),
                        started_at=existing.started_at,
                        lease_until=existing.lease_until,
                        sheet_id=sheet.id,
                        sheet_number=sheet.number,
                    )
                if current.role is StaffRole.ADMIN:
                    if current.staff is None:
                        raise ApiError(401, "AUTH_REQUIRED", "Sessiya haqiqiy emas")
                    if inquiry.assigned_to not in {None, current.staff.id}:
                        assignee = await db_session.get(StaffUser, inquiry.assigned_to)
                        assignee_name = assignee.full_name if assignee else "boshqa xodim"
                        raise ApiError(
                            409,
                            "INQUIRY_ASSIGNED",
                            f"Murojaat {assignee_name}ga biriktirilgan",
                        )
                    inquiry.assigned_to = current.staff.id
                in_progress = await db_session.scalar(
                    select(ContactAttempt).where(
                        ContactAttempt.inquiry_id == inquiry.id,
                        ContactAttempt.outcome == "in_progress",
                    )
                )
                if in_progress:
                    raise ApiError(
                        409, "CONTACT_IN_PROGRESS", "Bu murojaatda aloqa urinish davom etmoqda"
                    )
                patient = await db_session.get(Patient, inquiry.patient_id)
                if patient is None:
                    raise ApiError(404, "PATIENT_NOT_FOUND", "Bemor topilmadi")
                local_date = now.astimezone(BUSINESS_TIMEZONE).date()
                sheet = await db_session.scalar(
                    select(ReceptionSheet).where(
                        ReceptionSheet.inquiry_id == inquiry.id,
                        ReceptionSheet.local_contact_date == local_date,
                    )
                )
                if sheet is None:
                    sheet_id = uuid4()
                    sheet = ReceptionSheet(
                        id=sheet_id,
                        inquiry_id=inquiry.id,
                        local_contact_date=local_date,
                        number=f"RU-{local_date:%Y%m%d}-{sheet_id.hex[:8].upper()}",
                        contact_snapshot={
                            "patient_id": str(patient.id),
                            "full_name": patient.full_name,
                            "phone_e164": patient.phone_e164,
                            "telegram_user_id": patient.telegram_user_id,
                            "registered_at": inquiry.registered_at.isoformat(),
                            "reason": inquiry.reason,
                            "source": inquiry.source_snapshot,
                        },
                        created_by=current.staff.id if current.staff else None,
                        created_at=now,
                        updated_at=now,
                    )
                    db_session.add(sheet)
                    await db_session.flush()
                attempt = ContactAttempt(
                    inquiry_id=inquiry.id,
                    actor_id=current.staff.id if current.staff else None,
                    actor_key=actor_key,
                    idempotency_key=idempotency_key,
                    outcome="in_progress",
                    started_at=now,
                    lease_until=now + timedelta(minutes=30),
                    created_at=now,
                )
                db_session.add(attempt)
                await db_session.flush()
                db_session.add(SheetAttempt(sheet_id=sheet.id, attempt_id=attempt.id))
                inquiry.version += 1
                inquiry.updated_at = now
                add_audit(
                    db_session,
                    actor_kind=current.kind,
                    actor_id=current.actor_id,
                    action="contact.started",
                    entity_type="contact_attempt",
                    entity_id=attempt.id,
                    request_id=request.state.request_id,
                    occurred_at=now,
                )
        return ContactAttemptStartResponse(
            id=attempt.id,
            inquiry_id=inquiry.id,
            phone_e164=patient.phone_e164,
            outcome=ContactAttemptOutcome.IN_PROGRESS,
            started_at=attempt.started_at,
            lease_until=attempt.lease_until,
            sheet_id=sheet.id,
            sheet_number=sheet.number,
        )
    except IntegrityError as error:
        raise ApiError(409, "CONTACT_CONFLICT", "Aloqa urinishini boshqa xodim boshladi") from error


@router.post("/contact-attempts/{attempt_id}/finish", response_model=ContactAttemptResponse)
async def finish_contact_attempt(
    attempt_id: UUID,
    payload: ContactAttemptFinishRequest,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> ContactAttemptResponse:
    ensure_role(current, ALL_STAFF)
    require_csrf(request, settings, current)
    if payload.outcome is ContactAttemptOutcome.ANSWERED and not (payload.note or "").strip():
        raise ApiError(422, "ANSWERED_NOTE_REQUIRED", "Javob bergan suhbat uchun izoh yozing")
    now = datetime.now(UTC)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            attempt = await db_session.get(ContactAttempt, attempt_id, with_for_update=True)
            if attempt is None:
                raise ApiError(404, "ATTEMPT_NOT_FOUND", "Aloqa urinishi topilmadi")
            inquiry = await db_session.get(Inquiry, attempt.inquiry_id, with_for_update=True)
            if inquiry is None:
                raise ApiError(404, "INQUIRY_NOT_FOUND", "Murojaat topilmadi")
            if current.role is StaffRole.ADMIN and attempt.actor_id != current.staff.id:  # type: ignore[union-attr]
                raise ApiError(403, "OBJECT_FORBIDDEN", "Bu urinish sizga tegishli emas")
            if attempt.outcome not in {"in_progress", "interrupted"}:
                raise ApiError(409, "ATTEMPT_ALREADY_FINISHED", "Aloqa urinishi yakunlangan")
            attempt.outcome = payload.outcome.value
            attempt.answered_at = now if payload.outcome is ContactAttemptOutcome.ANSWERED else None
            attempt.ended_at = now
            attempt.lease_until = now
            inquiry.next_followup_at = payload.next_followup_at
            inquiry.version += 1
            inquiry.updated_at = now
            if payload.note and payload.note.strip():
                db_session.add(
                    ContactNote(
                        attempt_id=attempt.id,
                        author_id=current.staff.id if current.staff else None,
                        text=payload.note.strip(),
                        created_at=now,
                    )
                )
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action="contact.finished",
                entity_type="contact_attempt",
                entity_id=attempt.id,
                request_id=request.state.request_id,
                occurred_at=now,
                changes={"outcome": payload.outcome.value},
            )
    return ContactAttemptResponse(
        id=attempt.id,
        inquiry_id=attempt.inquiry_id,
        outcome=ContactAttemptOutcome(attempt.outcome),
        started_at=attempt.started_at,
        answered_at=attempt.answered_at,
        ended_at=attempt.ended_at,
    )


@router.post("/contact-attempts/{attempt_id}/notes", status_code=201)
async def add_contact_note(
    attempt_id: UUID,
    payload: ContactNoteRequest,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> dict[str, str]:
    ensure_role(current, ALL_STAFF)
    require_csrf(request, settings, current)
    if payload.previous_revision_id and not payload.revision_reason:
        raise ApiError(422, "REVISION_REASON_REQUIRED", "Tahrir sababini yozing")
    async with database.session_factory() as db_session:
        async with db_session.begin():
            attempt = await db_session.get(ContactAttempt, attempt_id)
            if attempt is None:
                raise ApiError(404, "ATTEMPT_NOT_FOUND", "Aloqa urinishi topilmadi")
            if payload.previous_revision_id:
                previous = await db_session.get(ContactNote, payload.previous_revision_id)
                if previous is None or previous.attempt_id != attempt.id:
                    raise ApiError(422, "INVALID_REVISION", "Oldingi izoh mos emas")
            note = ContactNote(
                attempt_id=attempt.id,
                author_id=current.staff.id if current.staff else None,
                text=payload.text.strip(),
                previous_revision_id=payload.previous_revision_id,
                revision_reason=payload.revision_reason,
                created_at=datetime.now(UTC),
            )
            db_session.add(note)
            await db_session.flush()
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action="contact.note_added",
                entity_type="contact_note",
                entity_id=note.id,
                request_id=request.state.request_id,
                occurred_at=datetime.now(UTC),
                changes={"revision": bool(payload.previous_revision_id)},
            )
    return {"id": str(note.id)}


@router.get("/reception-sheets/{sheet_id}", response_model=ReceptionSheetResponse)
@router.get("/reception-sheets/{sheet_id}/print-data", response_model=ReceptionSheetResponse)
async def reception_sheet(
    sheet_id: UUID,
    request: Request,
    current: PrincipalDependency,
    database: DatabaseDependency,
) -> ReceptionSheetResponse:
    ensure_role(current, ALL_STAFF)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            sheet = await db_session.get(ReceptionSheet, sheet_id)
            if sheet is None:
                raise ApiError(404, "SHEET_NOT_FOUND", "Qabul varaqasi topilmadi")
            attempts = list(
                (
                    await db_session.scalars(
                        select(ContactAttempt)
                        .join(SheetAttempt, SheetAttempt.attempt_id == ContactAttempt.id)
                        .where(SheetAttempt.sheet_id == sheet.id)
                        .order_by(ContactAttempt.started_at)
                    )
                ).all()
            )
            appointments = list(
                (
                    await db_session.scalars(
                        select(Appointment)
                        .where(Appointment.sheet_id == sheet.id)
                        .order_by(Appointment.start_at)
                    )
                ).all()
            )
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action="reception_sheet.print_viewed"
                if request.url.path.endswith("print-data")
                else "reception_sheet.viewed",
                entity_type="reception_sheet",
                entity_id=sheet.id,
                request_id=request.state.request_id,
                occurred_at=datetime.now(UTC),
            )
        snapshot = sheet.contact_snapshot
        return ReceptionSheetResponse(
            id=sheet.id,
            number=sheet.number,
            local_contact_date=sheet.local_contact_date,
            patient_name=str(snapshot.get("full_name") or ""),
            phone_e164=str(snapshot.get("phone_e164") or ""),
            attempts=[
                {
                    "id": str(attempt.id),
                    "outcome": attempt.outcome,
                    "started_at": attempt.started_at.isoformat(),
                    "answered_at": attempt.answered_at.isoformat() if attempt.answered_at else None,
                    "ended_at": attempt.ended_at.isoformat() if attempt.ended_at else None,
                }
                for attempt in attempts
            ],
            appointments=[
                {
                    "id": str(appointment.id),
                    "start_at": appointment.start_at.isoformat(),
                    "status": appointment.status,
                }
                for appointment in appointments
            ],
        )
