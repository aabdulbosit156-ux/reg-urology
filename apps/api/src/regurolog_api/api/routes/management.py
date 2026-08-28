import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import distinct, exists, func, select, text
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
from regurolog_api.contracts import StaffRole
from regurolog_api.crypto import qr_data_url
from regurolog_api.database import Database
from regurolog_api.domain.validation import (
    DomainValidationError,
    local_day_bounds_utc,
    mask_phone,
    render_template,
)
from regurolog_api.errors import ApiError
from regurolog_api.models import (
    Appointment,
    AppointmentEvent,
    AttributionEvent,
    AuditEvent,
    BotConnection,
    Campaign,
    ContactAttempt,
    Inquiry,
    Patient,
    SettingsVersion,
    StaffUser,
)
from regurolog_api.schemas import (
    ActivityLogItem,
    AdminResetRequest,
    AnalyticsResponse,
    CampaignCreateRequest,
    CampaignResponse,
    NoShowReportItem,
    SettingsDraftRequest,
    SettingsPublishRequest,
    SettingsVersionResponse,
    StaffActivityStat,
)
from regurolog_api.services.audit import add_audit
from regurolog_api.services.templates import DEFAULT_BOT_MESSAGES

router = APIRouter()
DatabaseDependency = Annotated[Database, Depends(get_database)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
PrincipalDependency = Annotated[CurrentPrincipal, Depends(require_principal)]
MANAGERS = {StaffRole.DEV, StaffRole.DIRECTOR}
ALL_STAFF = {StaffRole.DEV, StaffRole.DIRECTOR, StaffRole.ADMIN}


async def _bot_username(db_session: AsyncSession) -> str | None:
    username = await db_session.scalar(
        select(BotConnection.username).where(BotConnection.active.is_(True)).limit(1)
    )
    return str(username) if username is not None else None


def _campaign_response(campaign: Campaign, bot_username: str | None) -> CampaignResponse:
    deep_link = f"https://t.me/{bot_username}?start=src_{campaign.code}" if bot_username else None
    return CampaignResponse(
        id=campaign.id,
        code=campaign.code,
        name=campaign.name,
        utm_source=campaign.utm_source,
        utm_medium=campaign.utm_medium,
        utm_campaign=campaign.utm_campaign,
        utm_content=campaign.utm_content,
        utm_term=campaign.utm_term,
        deep_link=deep_link,
        qr_data_url=qr_data_url(deep_link) if deep_link else None,
        archived_at=campaign.archived_at,
        revoked_at=campaign.revoked_at,
    )


@router.get("/campaigns", response_model=list[CampaignResponse])
async def list_campaigns(
    current: PrincipalDependency, database: DatabaseDependency
) -> list[CampaignResponse]:
    ensure_role(current, MANAGERS)
    async with database.session_factory() as db_session:
        campaigns = list(
            (await db_session.scalars(select(Campaign).order_by(Campaign.created_at.desc()))).all()
        )
        username = await _bot_username(db_session)
    return [_campaign_response(item, username) for item in campaigns]


@router.post("/campaigns", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    payload: CampaignCreateRequest,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> CampaignResponse:
    ensure_role(current, MANAGERS)
    require_csrf(request, settings, current)
    now = datetime.now(UTC)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            for _ in range(5):
                code = secrets.token_hex(6)
                if not await db_session.scalar(select(Campaign.id).where(Campaign.code == code)):
                    break
            else:
                raise ApiError(503, "CAMPAIGN_CODE_UNAVAILABLE", "Kampaniya kodi yaratilmadi")
            campaign = Campaign(
                code=code,
                name=payload.name.strip(),
                utm_source=payload.utm_source.strip(),
                utm_medium=payload.utm_medium.strip(),
                utm_campaign=payload.utm_campaign.strip(),
                utm_content=payload.utm_content.strip() if payload.utm_content else None,
                utm_term=payload.utm_term.strip() if payload.utm_term else None,
                created_by=current.staff.id if current.staff else None,
                created_at=now,
                updated_at=now,
            )
            db_session.add(campaign)
            await db_session.flush()
            username = await _bot_username(db_session)
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action="campaign.created",
                entity_type="campaign",
                entity_id=campaign.id,
                request_id=request.state.request_id,
                occurred_at=now,
            )
    return _campaign_response(campaign, username)


@router.post("/campaigns/{campaign_id}/archive", response_model=CampaignResponse)
async def archive_campaign(
    campaign_id: UUID,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
    revoke: bool = False,
) -> CampaignResponse:
    ensure_role(current, MANAGERS)
    require_csrf(request, settings, current)
    now = datetime.now(UTC)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            campaign = await db_session.get(Campaign, campaign_id, with_for_update=True)
            if campaign is None:
                raise ApiError(404, "CAMPAIGN_NOT_FOUND", "Kampaniya topilmadi")
            campaign.archived_at = campaign.archived_at or now
            if revoke:
                campaign.revoked_at = now
            campaign.updated_at = now
            username = await _bot_username(db_session)
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action="campaign.revoked" if revoke else "campaign.archived",
                entity_type="campaign",
                entity_id=campaign.id,
                request_id=request.state.request_id,
                occurred_at=now,
            )
    return _campaign_response(campaign, username)


def _settings_response(version: SettingsVersion) -> SettingsVersionResponse:
    return SettingsVersionResponse(
        id=version.id,
        namespace=version.namespace,
        payload=version.payload,
        version=version.version,
        state=version.state,
        published_at=version.published_at,
    )


@router.get("/settings", response_model=list[SettingsVersionResponse])
async def list_settings(
    current: PrincipalDependency, database: DatabaseDependency
) -> list[SettingsVersionResponse]:
    ensure_role(current, MANAGERS)
    async with database.session_factory() as db_session:
        versions = list(
            (
                await db_session.scalars(
                    select(SettingsVersion).order_by(
                        SettingsVersion.namespace, SettingsVersion.version.desc()
                    )
                )
            ).all()
        )
    return [_settings_response(item) for item in versions]


@router.patch("/settings", response_model=SettingsVersionResponse)
async def create_settings_draft(
    payload: SettingsDraftRequest,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> SettingsVersionResponse:
    ensure_role(current, MANAGERS)
    require_csrf(request, settings, current)
    if payload.namespace == "bot_messages":
        unknown = set(payload.payload) - set(DEFAULT_BOT_MESSAGES)
        if unknown:
            raise ApiError(422, "UNKNOWN_TEMPLATE_KEY", "Noma’lum bot matni kaliti")
        try:
            for value in payload.payload.values():
                if not isinstance(value, str):
                    raise DomainValidationError("payload", "Bot matnlari string bo‘lishi kerak")
                render_template(
                    value,
                    {
                        "full_name": "Bemor",
                        "doctor_name": "Doktor",
                        "date": "2026-08-26",
                        "time": "09:00",
                        "clinic_address": "Klinika",
                    },
                )
        except DomainValidationError as error:
            raise ApiError(422, "INVALID_TEMPLATE", error.message) from error
    if payload.namespace == "notifications":
        unknown = set(payload.payload) - {"reminders_enabled", "reminder_hours"}
        enabled = payload.payload.get("reminders_enabled", True)
        hours = payload.payload.get("reminder_hours", [24, 2])
        if (
            unknown
            or not isinstance(enabled, bool)
            or not isinstance(hours, list)
            or not 1 <= len(hours) <= 4
            or any(
                isinstance(item, bool) or not isinstance(item, int) or not 1 <= item <= 168
                for item in hours
            )
            or len(set(hours)) != len(hours)
        ):
            raise ApiError(
                422,
                "INVALID_NOTIFICATION_SETTINGS",
                "Reminder sozlamalari noto‘g‘ri",
            )
    now = datetime.now(UTC)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            await db_session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:namespace))"),
                {"namespace": payload.namespace},
            )
            latest = await db_session.scalar(
                select(func.max(SettingsVersion.version)).where(
                    SettingsVersion.namespace == payload.namespace
                )
            )
            version = SettingsVersion(
                namespace=payload.namespace,
                payload=payload.payload,
                version=int(latest or 0) + 1,
                state="draft",
                actor_id=current.staff.id if current.staff else None,
                created_at=now,
            )
            db_session.add(version)
            await db_session.flush()
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action="settings.draft_created",
                entity_type="settings_version",
                entity_id=version.id,
                request_id=request.state.request_id,
                occurred_at=now,
                changes={"namespace": payload.namespace, "version": version.version},
            )
    return _settings_response(version)


@router.post("/settings/{version_id}/rollback", response_model=SettingsVersionResponse)
async def rollback_settings(
    version_id: UUID,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> SettingsVersionResponse:
    ensure_role(current, MANAGERS)
    require_csrf(request, settings, current)
    now = datetime.now(UTC)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            source = await db_session.get(SettingsVersion, version_id)
            if source is None:
                raise ApiError(404, "SETTINGS_VERSION_NOT_FOUND", "Sozlama versiyasi topilmadi")
            await db_session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:namespace))"),
                {"namespace": source.namespace},
            )
            latest = await db_session.scalar(
                select(func.max(SettingsVersion.version)).where(
                    SettingsVersion.namespace == source.namespace
                )
            )
            version = SettingsVersion(
                namespace=source.namespace,
                payload=source.payload,
                version=int(latest or 0) + 1,
                state="draft",
                actor_id=current.staff.id if current.staff else None,
                created_at=now,
            )
            db_session.add(version)
            await db_session.flush()
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action="settings.rollback_draft_created",
                entity_type="settings_version",
                entity_id=version.id,
                request_id=request.state.request_id,
                occurred_at=now,
                changes={"source_version": source.version, "new_version": version.version},
            )
    return _settings_response(version)


@router.post("/settings/publish", response_model=SettingsVersionResponse)
async def publish_settings(
    payload: SettingsPublishRequest,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> SettingsVersionResponse:
    ensure_role(current, MANAGERS)
    require_csrf(request, settings, current)
    now = datetime.now(UTC)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            version = await db_session.get(
                SettingsVersion, payload.version_id, with_for_update=True
            )
            if version is None:
                raise ApiError(404, "SETTINGS_VERSION_NOT_FOUND", "Sozlama versiyasi topilmadi")
            if version.state != "draft":
                raise ApiError(409, "SETTINGS_ALREADY_PUBLISHED", "Versiya draft emas")
            await db_session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:namespace))"),
                {"namespace": version.namespace},
            )
            previous = list(
                (
                    await db_session.scalars(
                        select(SettingsVersion)
                        .where(
                            SettingsVersion.namespace == version.namespace,
                            SettingsVersion.state == "published",
                        )
                        .with_for_update()
                    )
                ).all()
            )
            for old in previous:
                old.state = "archived"
            version.state = "published"
            version.published_at = now
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action="settings.published",
                entity_type="settings_version",
                entity_id=version.id,
                request_id=request.state.request_id,
                occurred_at=now,
                changes={"namespace": version.namespace, "version": version.version},
            )
    return _settings_response(version)


def _date_range(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    if date_to < date_from or (date_to - date_from).days > 366:
        raise ApiError(422, "INVALID_DATE_RANGE", "Sana oralig‘i noto‘g‘ri")
    start, _ = local_day_bounds_utc(date_from)
    _, end = local_day_bounds_utc(date_to)
    return start, end


@router.get("/analytics/cohort", response_model=AnalyticsResponse)
async def cohort_analytics(
    date_from: date,
    date_to: date,
    current: PrincipalDependency,
    database: DatabaseDependency,
) -> AnalyticsResponse:
    ensure_role(current, MANAGERS)
    start, end = _date_range(date_from, date_to)
    cohort = (
        select(Inquiry.id)
        .where(Inquiry.registered_at >= start, Inquiry.registered_at < end)
        .subquery()
    )
    cohort_ids = select(cohort.c.id)
    async with database.session_factory() as db_session:
        inquiries = int((await db_session.scalar(select(func.count()).select_from(cohort))) or 0)
        new_patients = int(
            (
                await db_session.scalar(
                    select(func.count(Patient.id)).where(
                        Patient.first_registered_at >= start, Patient.first_registered_at < end
                    )
                )
            )
            or 0
        )
        starts_total = int(
            (
                await db_session.scalar(
                    select(func.count(AttributionEvent.id)).where(
                        AttributionEvent.event_type == "start",
                        AttributionEvent.occurred_at >= start,
                        AttributionEvent.occurred_at < end,
                    )
                )
            )
            or 0
        )
        starts_unique = int(
            (
                await db_session.scalar(
                    select(func.count(distinct(AttributionEvent.telegram_user_id))).where(
                        AttributionEvent.event_type == "start",
                        AttributionEvent.occurred_at >= start,
                        AttributionEvent.occurred_at < end,
                    )
                )
            )
            or 0
        )
        contact_started = int(
            (
                await db_session.scalar(
                    select(func.count(distinct(ContactAttempt.inquiry_id))).where(
                        ContactAttempt.inquiry_id.in_(cohort_ids)
                    )
                )
            )
            or 0
        )
        answered = int(
            (
                await db_session.scalar(
                    select(func.count(distinct(ContactAttempt.inquiry_id))).where(
                        ContactAttempt.inquiry_id.in_(cohort_ids),
                        ContactAttempt.outcome == "answered",
                    )
                )
            )
            or 0
        )
        answered_not_booked = int(
            (
                await db_session.scalar(
                    select(func.count(Inquiry.id)).where(
                        Inquiry.id.in_(cohort_ids),
                        Inquiry.status == "open",
                        exists().where(
                            ContactAttempt.inquiry_id == Inquiry.id,
                            ContactAttempt.outcome == "answered",
                        ),
                        ~exists().where(
                            Appointment.inquiry_id == Inquiry.id,
                            Appointment.status.in_(["scheduled", "checked_in"]),
                        ),
                    )
                )
            )
            or 0
        )
        booked = int(
            (
                await db_session.scalar(
                    select(func.count(distinct(Appointment.inquiry_id))).where(
                        Appointment.inquiry_id.in_(cohort_ids)
                    )
                )
            )
            or 0
        )
        active = int(
            (
                await db_session.scalar(
                    select(func.count(distinct(Appointment.inquiry_id))).where(
                        Appointment.inquiry_id.in_(cohort_ids),
                        Appointment.status.in_(["scheduled", "checked_in"]),
                    )
                )
            )
            or 0
        )
        followup_due = int(
            (
                await db_session.scalar(
                    select(func.count(Inquiry.id)).where(
                        Inquiry.id.in_(cohort_ids),
                        Inquiry.status == "open",
                        Inquiry.next_followup_at <= datetime.now(UTC),
                        ~exists().where(
                            Appointment.inquiry_id == Inquiry.id,
                            Appointment.status.in_(["scheduled", "checked_in"]),
                        ),
                    )
                )
            )
            or 0
        )
        first_contact = (
            select(
                ContactAttempt.inquiry_id,
                func.min(ContactAttempt.started_at).label("first_at"),
            )
            .where(ContactAttempt.inquiry_id.in_(cohort_ids))
            .group_by(ContactAttempt.inquiry_id)
            .subquery()
        )
        delay_seconds = func.extract("epoch", first_contact.c.first_at - Inquiry.registered_at)
        speed_row = (
            await db_session.execute(
                select(
                    func.percentile_cont(0.5).within_group(delay_seconds),
                    func.percentile_cont(0.9).within_group(delay_seconds),
                )
                .join(first_contact, first_contact.c.inquiry_id == Inquiry.id)
                .where(Inquiry.id.in_(cohort_ids))
            )
        ).one()
        source_label = func.coalesce(
            Inquiry.source_snapshot["name"].astext,
            Inquiry.source_snapshot["kind"].astext,
            "organic",
        ).label("source")
        utm_rows = (
            await db_session.execute(
                select(
                    source_label,
                    func.count(distinct(Inquiry.id)).label("inquiries"),
                    func.count(distinct(Appointment.inquiry_id)).label("booked"),
                )
                .outerjoin(Appointment, Appointment.inquiry_id == Inquiry.id)
                .where(Inquiry.id.in_(cohort_ids))
                .group_by(source_label)
                .order_by(func.count(distinct(Inquiry.id)).desc())
            )
        ).all()
        daily_rows = (
            await db_session.execute(
                select(
                    func.date(func.timezone("Asia/Tashkent", Inquiry.registered_at)).label("day"),
                    func.count(Inquiry.id),
                )
                .where(Inquiry.registered_at >= start, Inquiry.registered_at < end)
                .group_by("day")
            )
        ).all()
    daily_map = {row[0]: int(row[1]) for row in daily_rows}
    daily: list[dict[str, Any]] = []
    cursor = date_from
    while cursor <= date_to:
        daily.append({"date": cursor.isoformat(), "inquiries": daily_map.get(cursor, 0)})
        cursor += timedelta(days=1)
    return AnalyticsResponse(
        mode="registration_cohort",
        date_from=date_from,
        date_to=date_to,
        metrics={
            "new_patients": new_patients,
            "inquiries": inquiries,
            "bot_starts_total": starts_total,
            "bot_starts_unique": starts_unique,
            "not_contacted": max(0, inquiries - contact_started),
            "contact_started": contact_started,
            "answered": answered,
            "answered_not_booked": answered_not_booked,
            "booked": booked,
            "active_appointments": active,
            "followup_due": followup_due,
            "first_contact_median_minutes": (
                round(float(speed_row[0]) / 60, 2) if speed_row[0] is not None else None
            ),
            "first_contact_p90_minutes": (
                round(float(speed_row[1]) / 60, 2) if speed_row[1] is not None else None
            ),
        },
        daily=daily,
        breakdowns={
            "utm": [
                {
                    "source": source,
                    "inquiries": int(source_inquiries),
                    "booked": int(source_booked),
                }
                for source, source_inquiries, source_booked in utm_rows
            ]
        },
    )


@router.get("/analytics/activity", response_model=AnalyticsResponse)
async def activity_analytics(
    date_from: date,
    date_to: date,
    current: PrincipalDependency,
    database: DatabaseDependency,
) -> AnalyticsResponse:
    ensure_role(current, ALL_STAFF)
    start, end = _date_range(date_from, date_to)
    attempt_filters = [ContactAttempt.started_at >= start, ContactAttempt.started_at < end]
    appointment_filters = [Appointment.start_at >= start, Appointment.start_at < end]
    if current.role is StaffRole.ADMIN:
        if current.staff is None:
            raise ApiError(401, "AUTH_REQUIRED", "Sessiya haqiqiy emas")
        attempt_filters.append(ContactAttempt.actor_id == current.staff.id)
        appointment_filters.append(Appointment.created_by == current.staff.id)
    async with database.session_factory() as db_session:
        attempts = int(
            (await db_session.scalar(select(func.count(ContactAttempt.id)).where(*attempt_filters)))
            or 0
        )
        answered = int(
            (
                await db_session.scalar(
                    select(func.count(ContactAttempt.id)).where(
                        *attempt_filters, ContactAttempt.outcome == "answered"
                    )
                )
            )
            or 0
        )
        appointments = int(
            (
                await db_session.scalar(
                    select(func.count(Appointment.id)).where(*appointment_filters)
                )
            )
            or 0
        )
        completed = int(
            (
                await db_session.scalar(
                    select(func.count(Appointment.id)).where(
                        *appointment_filters, Appointment.status == "completed"
                    )
                )
            )
            or 0
        )
        no_show = int(
            (
                await db_session.scalar(
                    select(func.count(Appointment.id)).where(
                        *appointment_filters, Appointment.status == "no_show"
                    )
                )
            )
            or 0
        )
        checked_in = int(
            (
                await db_session.scalar(
                    select(func.count(Appointment.id)).where(
                        *appointment_filters, Appointment.status == "checked_in"
                    )
                )
            )
            or 0
        )
        operator_rows = (
            await db_session.execute(
                select(
                    StaffUser.full_name,
                    func.count(ContactAttempt.id),
                    func.count(ContactAttempt.id).filter(ContactAttempt.outcome == "answered"),
                )
                .outerjoin(StaffUser, StaffUser.id == ContactAttempt.actor_id)
                .where(*attempt_filters)
                .group_by(StaffUser.full_name)
                .order_by(func.count(ContactAttempt.id).desc())
            )
        ).all()
        daily_rows = (
            await db_session.execute(
                select(
                    func.date(func.timezone("Asia/Tashkent", ContactAttempt.started_at)).label(
                        "day"
                    ),
                    func.count(ContactAttempt.id),
                )
                .where(*attempt_filters)
                .group_by("day")
            )
        ).all()
    denominator = completed + checked_in + no_show
    daily_map = {row[0]: int(row[1]) for row in daily_rows}
    daily: list[dict[str, Any]] = []
    cursor = date_from
    while cursor <= date_to:
        daily.append({"date": cursor.isoformat(), "attempts": daily_map.get(cursor, 0)})
        cursor += timedelta(days=1)
    return AnalyticsResponse(
        mode="operational_activity",
        date_from=date_from,
        date_to=date_to,
        metrics={
            "contact_attempts": attempts,
            "answered": answered,
            "appointments": appointments,
            "completed": completed,
            "checked_in": checked_in,
            "no_show": no_show,
            "no_show_rate": round(no_show / denominator * 100, 2) if denominator else None,
        },
        daily=daily,
        breakdowns={
            "operators": [
                {
                    "operator": operator_name or "Tizim operatori",
                    "attempts": int(operator_attempts),
                    "answered": int(operator_answered),
                }
                for operator_name, operator_attempts, operator_answered in operator_rows
            ]
        },
    )


@router.get("/reports/no-shows", response_model=list[NoShowReportItem])
async def no_show_report(
    date_from: date,
    date_to: date,
    current: PrincipalDependency,
    database: DatabaseDependency,
) -> list[NoShowReportItem]:
    ensure_role(current, MANAGERS)
    start, end = _date_range(date_from, date_to)
    rescheduled = exists().where(
        AppointmentEvent.appointment_id == Appointment.id,
        AppointmentEvent.action == "rescheduled",
    )
    statement = (
        select(
            Appointment,
            Patient,
            StaffUser.full_name,
            Inquiry.source_snapshot,
            rescheduled.label("rescheduled"),
        )
        .join(Inquiry, Inquiry.id == Appointment.inquiry_id)
        .join(Patient, Patient.id == Inquiry.patient_id)
        .outerjoin(StaffUser, StaffUser.id == Inquiry.assigned_to)
        .where(
            Appointment.status == "no_show",
            Appointment.start_at >= start,
            Appointment.start_at < end,
        )
        .order_by(Appointment.start_at.desc())
    )
    async with database.session_factory() as db_session:
        rows = (await db_session.execute(statement)).all()
    return [
        NoShowReportItem(
            appointment_id=appointment.id,
            patient_name=patient.full_name,
            phone_masked=mask_phone(patient.phone_e164),
            operator_name=operator_name,
            start_at=appointment.start_at,
            source=str(source.get("name") or source.get("kind") or "organic"),
            rescheduled=bool(was_rescheduled),
        )
        for appointment, patient, operator_name, source, was_rescheduled in rows
    ]


def _safe_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


@router.get("/activity/staff-stats", response_model=list[StaffActivityStat])
async def staff_activity_stats(
    current: PrincipalDependency, database: DatabaseDependency
) -> list[StaffActivityStat]:
    """Per-staff totals: appointments booked and audit actions performed."""

    ensure_role(current, MANAGERS)
    async with database.session_factory() as db_session:
        appointment_rows = (
            await db_session.execute(
                select(Appointment.created_by, func.count(Appointment.id))
                .where(Appointment.created_by.is_not(None))
                .group_by(Appointment.created_by)
            )
        ).all()
        action_rows = (
            await db_session.execute(
                select(AuditEvent.actor_id, func.count(AuditEvent.id))
                .where(AuditEvent.actor_kind == "staff", AuditEvent.actor_id.is_not(None))
                .group_by(AuditEvent.actor_id)
            )
        ).all()
        staff = list(
            (await db_session.scalars(select(StaffUser).order_by(StaffUser.full_name))).all()
        )
    appointment_map = {row[0]: int(row[1]) for row in appointment_rows}
    action_map = {row[0]: int(row[1]) for row in action_rows}
    return [
        StaffActivityStat(
            staff_id=member.id,
            full_name=member.full_name,
            role=StaffRole(member.role),
            state=member.state,
            appointments_created=appointment_map.get(member.id, 0),
            actions=action_map.get(str(member.id), 0),
        )
        for member in staff
    ]


@router.get("/activity/logs", response_model=list[ActivityLogItem])
async def activity_logs(
    current: PrincipalDependency,
    database: DatabaseDependency,
    actor_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[ActivityLogItem]:
    """Recent audit trail, newest first, optionally filtered by one staff actor."""

    ensure_role(current, MANAGERS)
    filters = []
    if actor_id is not None:
        filters.append(AuditEvent.actor_id == str(actor_id))
    async with database.session_factory() as db_session:
        events = list(
            (
                await db_session.scalars(
                    select(AuditEvent)
                    .where(*filters)
                    .order_by(AuditEvent.occurred_at.desc())
                    .limit(limit)
                )
            ).all()
        )
        staff_uuids = [
            parsed
            for event in events
            if event.actor_kind == "staff"
            and (parsed := _safe_uuid(event.actor_id)) is not None
        ]
        names: dict[str, str] = {}
        if staff_uuids:
            name_rows = (
                await db_session.execute(
                    select(StaffUser.id, StaffUser.full_name).where(StaffUser.id.in_(staff_uuids))
                )
            ).all()
            names = {str(row[0]): row[1] for row in name_rows}
    return [
        ActivityLogItem(
            id=event.id,
            occurred_at=event.occurred_at,
            actor_kind=event.actor_kind,
            actor_name=(
                names.get(event.actor_id)
                if event.actor_kind == "staff" and event.actor_id
                else None
            ),
            action=event.action,
            entity_type=event.entity_type,
            note=event.note,
        )
        for event in events
    ]


# Ordered SQL for each destructive reset scope (children before parents).
_RESET_STATEMENTS: dict[str, tuple[str, ...]] = {
    "calendar": (
        "DELETE FROM appointment_events",
        "DELETE FROM appointments",
        "DELETE FROM day_overrides",
        "DELETE FROM schedule_blocks",
        "DELETE FROM work_schedule_versions",
        "DELETE FROM outbox_jobs WHERE kind LIKE 'appointment_%'",
    ),
    "patients": (
        "DELETE FROM consents",
        "DELETE FROM contact_notes",
        "DELETE FROM sheet_attempts",
        "DELETE FROM appointment_events",
        "DELETE FROM appointments",
        "DELETE FROM contact_attempts",
        "DELETE FROM reception_sheets",
        "DELETE FROM inquiries",
        "DELETE FROM registration_drafts",
        "DELETE FROM attribution_events",
        "DELETE FROM patients",
    ),
    "staff": (
        # Null every actor reference before removing the staff rows themselves.
        "UPDATE staff_users SET invited_by = NULL",
        "UPDATE campaigns SET created_by = NULL",
        "UPDATE inquiries SET assigned_to = NULL",
        "UPDATE reception_sheets SET created_by = NULL",
        "UPDATE contact_attempts SET actor_id = NULL",
        "UPDATE contact_notes SET author_id = NULL",
        "UPDATE work_schedule_versions SET created_by = NULL",
        "UPDATE day_overrides SET created_by = NULL",
        "UPDATE schedule_blocks SET created_by = NULL",
        "UPDATE appointments SET created_by = NULL",
        "UPDATE appointment_events SET actor_id = NULL",
        "UPDATE settings_versions SET actor_id = NULL",
        "DELETE FROM auth_challenges",
        "DELETE FROM staff_invites",
        # Staff sessions cascade-delete; root sessions are untouched.
        "DELETE FROM staff_users",
    ),
}


@router.post("/admin/reset/{scope}")
async def reset_data(
    scope: str,
    payload: AdminResetRequest,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> dict[str, str]:
    """Destructive reset of a data scope. Guarded by role and a typed confirmation."""

    if scope not in _RESET_STATEMENTS:
        raise ApiError(404, "UNKNOWN_RESET_SCOPE", "Noma'lum tozalash bo'limi")
    if scope == "staff":
        if current.kind != "root":
            raise ApiError(
                403, "ROOT_REQUIRED", "Xodimlar bazasini faqat root operator tozalashi mumkin"
            )
    else:
        ensure_role(current, MANAGERS)
    require_csrf(request, settings, current)
    if payload.confirm.strip() != "TOZALASH":
        raise ApiError(422, "CONFIRM_REQUIRED", "Tasdiqlash uchun TOZALASH deb yozing")
    async with database.session_factory() as db_session:
        async with db_session.begin():
            for statement in _RESET_STATEMENTS[scope]:
                await db_session.execute(text(statement))
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action=f"admin.reset_{scope}",
                entity_type="database",
                entity_id=None,
                request_id=request.state.request_id,
                occurred_at=datetime.now(UTC),
            )
    return {"status": "ok", "scope": scope}
