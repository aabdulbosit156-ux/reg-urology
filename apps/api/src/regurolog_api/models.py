from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from regurolog_api.database import Base


def uuid_column() -> Mapped[UUID]:
    return mapped_column(primary_key=True, default=uuid4)


class StaffUser(Base):
    __tablename__ = "staff_users"
    __table_args__ = (
        CheckConstraint("role IN ('DIRECTOR','ADMIN')", name="role"),
        CheckConstraint("state IN ('active','inactive')", name="state"),
        Index("ix_staff_users_state_role", "state", "role"),
    )

    id: Mapped[UUID] = uuid_column()
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(16), default="active")
    auth_epoch: Mapped[str] = mapped_column(String(64), default=lambda: uuid4().hex)
    invited_by: Mapped[UUID | None] = mapped_column(ForeignKey("staff_users.id"))
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("principal_type IN ('root','staff')", name="principal_type"),
        Index("ix_sessions_expires_at", "expires_at"),
        Index("ix_sessions_staff_active", "staff_id", "revoked_at"),
    )

    id: Mapped[UUID] = uuid_column()
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    principal_type: Mapped[str] = mapped_column(String(16), default="root")
    staff_id: Mapped[UUID | None] = mapped_column(ForeignKey("staff_users.id", ondelete="CASCADE"))
    auth_epoch: Mapped[str] = mapped_column(String(64))
    csrf_token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StaffInvite(Base):
    __tablename__ = "staff_invites"
    __table_args__ = (
        CheckConstraint("role IN ('DIRECTOR','ADMIN')", name="role"),
        Index("ix_staff_invites_issuer_state", "issuer_id", "approved_at", "revoked_at"),
    )

    id: Mapped[UUID] = uuid_column()
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    role: Mapped[str] = mapped_column(String(16))
    issuer_kind: Mapped[str] = mapped_column(String(16))
    issuer_id: Mapped[UUID | None] = mapped_column(ForeignKey("staff_users.id"))
    claimed_by: Mapped[UUID | None] = mapped_column(ForeignKey("staff_users.id"))
    claimed_telegram_user_id: Mapped[int | None] = mapped_column(BigInteger)
    claimed_full_name: Mapped[str | None] = mapped_column(String(120))
    claimed_username: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuthChallenge(Base):
    __tablename__ = "auth_challenges"
    __table_args__ = (
        CheckConstraint(
            "state IN ('pending','awaiting_confirmation','approved','rejected',"
            "'consumed','expired')",
            name="state",
        ),
        Index("ix_auth_challenges_binding_state", "browser_binding_hash", "state"),
    )

    id: Mapped[UUID] = uuid_column()
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    browser_binding_hash: Mapped[str] = mapped_column(String(64), unique=True)
    matching_code: Mapped[str] = mapped_column(String(8))
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger)
    staff_id: Mapped[UUID | None] = mapped_column(ForeignKey("staff_users.id"))
    state: Mapped[str] = mapped_column(String(32), default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuthThrottle(Base):
    __tablename__ = "auth_throttles"
    __table_args__ = (CheckConstraint("failure_count >= 0", name="failure_count_nonnegative"),)

    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BotConnection(Base):
    __tablename__ = "bot_connections"
    __table_args__ = (
        CheckConstraint(
            "status IN ('connecting','connected','error','reconnect_required')", name="status"
        ),
        Index("ix_bot_connections_status", "status"),
    )

    id: Mapped[UUID] = uuid_column()
    bot_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    username: Mapped[str] = mapped_column(String(64))
    display_name: Mapped[str] = mapped_column(String(120))
    encrypted_token: Mapped[str] = mapped_column(Text)
    webhook_path_hash: Mapped[str] = mapped_column(String(64), unique=True)
    webhook_secret_hash: Mapped[str] = mapped_column(String(64))
    config_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32))
    last_update_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(240))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BotChatBinding(Base):
    __tablename__ = "bot_chat_bindings"
    __table_args__ = (
        UniqueConstraint(
            "bot_id",
            "telegram_user_id",
            name="uq_bot_chat_bindings_bot_user",
        ),
    )

    id: Mapped[UUID] = uuid_column()
    bot_id: Mapped[int] = mapped_column(BigInteger)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    reachable: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Campaign(Base):
    __tablename__ = "campaigns"
    __table_args__ = (Index("ix_campaigns_active", "archived_at", "revoked_at"),)

    id: Mapped[UUID] = uuid_column()
    code: Mapped[str] = mapped_column(String(24), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    utm_source: Mapped[str] = mapped_column(String(120))
    utm_medium: Mapped[str] = mapped_column(String(120))
    utm_campaign: Mapped[str] = mapped_column(String(120))
    utm_content: Mapped[str | None] = mapped_column(String(120))
    utm_term: Mapped[str | None] = mapped_column(String(120))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("staff_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AttributionEvent(Base):
    __tablename__ = "attribution_events"
    __table_args__ = (
        Index("ix_attribution_campaign_occurred", "campaign_id", "occurred_at"),
        Index("ix_attribution_user_occurred", "telegram_user_id", "occurred_at"),
    )

    id: Mapped[UUID] = uuid_column()
    bot_id: Mapped[int] = mapped_column(BigInteger)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger)
    campaign_id: Mapped[UUID | None] = mapped_column(ForeignKey("campaigns.id"))
    source_kind: Mapped[str] = mapped_column(String(24))
    event_type: Mapped[str] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        Index("ix_patients_phone_e164", "phone_e164"),
        Index("ix_patients_full_name", "full_name"),
    )

    id: Mapped[UUID] = uuid_column()
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    phone_e164: Mapped[str] = mapped_column(String(13))
    phone_source: Mapped[str] = mapped_column(String(16))
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    possible_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    first_source_id: Mapped[UUID | None] = mapped_column(ForeignKey("campaigns.id"))
    last_touch_source_id: Mapped[UUID | None] = mapped_column(ForeignKey("campaigns.id"))
    first_registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Doctor(Base):
    __tablename__ = "doctors"
    __table_args__ = (CheckConstraint("slot_minutes BETWEEN 5 AND 240", name="slot_minutes_range"),)

    id: Mapped[UUID] = uuid_column()
    name: Mapped[str] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Tashkent")
    slot_minutes: Mapped[int] = mapped_column(Integer, default=15, server_default="15")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    clinic_address: Mapped[str | None] = mapped_column(String(240))
    directions: Mapped[str | None] = mapped_column(Text)
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RegistrationDraft(Base):
    __tablename__ = "registration_drafts"
    __table_args__ = (
        UniqueConstraint(
            "bot_id",
            "telegram_user_id",
            name="uq_registration_drafts_bot_user",
        ),
        Index("ix_registration_drafts_expires", "expires_at"),
    )

    id: Mapped[UUID] = uuid_column()
    bot_id: Mapped[int] = mapped_column(BigInteger)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    step: Mapped[str] = mapped_column(String(32))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    attribution_id: Mapped[UUID | None] = mapped_column(ForeignKey("campaigns.id"))
    attribution_kind: Mapped[str] = mapped_column(String(24), default="organic")
    template_version: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[UUID] = uuid_column()
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    draft_id: Mapped[UUID | None] = mapped_column(ForeignKey("registration_drafts.id"))
    version: Mapped[int] = mapped_column(Integer)
    purpose: Mapped[str] = mapped_column(String(120))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Inquiry(Base):
    __tablename__ = "inquiries"
    __table_args__ = (
        CheckConstraint("status IN ('open','closed')", name="status"),
        Index(
            "uq_inquiries_patient_doctor_open",
            "patient_id",
            "doctor_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
        Index("ix_inquiries_status_registered", "status", "registered_at"),
        Index("ix_inquiries_assigned_status", "assigned_to", "status"),
        Index("ix_inquiries_followup", "next_followup_at"),
    )

    id: Mapped[UUID] = uuid_column()
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"))
    doctor_id: Mapped[UUID] = mapped_column(ForeignKey("doctors.id"))
    status: Mapped[str] = mapped_column(String(16), default="open")
    close_reason: Mapped[str | None] = mapped_column(String(32))
    assigned_to: Mapped[UUID | None] = mapped_column(ForeignKey("staff_users.id"))
    reason: Mapped[str | None] = mapped_column(Text)
    contact_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    source_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_followup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReceptionSheet(Base):
    __tablename__ = "reception_sheets"
    __table_args__ = (
        UniqueConstraint("inquiry_id", "local_contact_date", name="inquiry_local_date"),
    )

    id: Mapped[UUID] = uuid_column()
    inquiry_id: Mapped[UUID] = mapped_column(ForeignKey("inquiries.id"))
    local_contact_date: Mapped[date] = mapped_column(Date)
    number: Mapped[str] = mapped_column(String(40), unique=True)
    contact_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("staff_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ContactAttempt(Base):
    __tablename__ = "contact_attempts"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('in_progress','answered','no_answer','busy','unreachable',"
            "'wrong_number','aborted','interrupted')",
            name="outcome",
        ),
        Index(
            "uq_contact_attempts_inquiry_in_progress",
            "inquiry_id",
            unique=True,
            postgresql_where=text("outcome = 'in_progress'"),
        ),
        Index("ix_contact_attempts_inquiry_started", "inquiry_id", "started_at"),
        UniqueConstraint("actor_key", "idempotency_key", name="actor_idempotency"),
    )

    id: Mapped[UUID] = uuid_column()
    inquiry_id: Mapped[UUID] = mapped_column(ForeignKey("inquiries.id"))
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("staff_users.id"))
    actor_key: Mapped[str] = mapped_column(String(80))
    idempotency_key: Mapped[str] = mapped_column(String(80))
    outcome: Mapped[str] = mapped_column(String(24), default="in_progress")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ContactNote(Base):
    __tablename__ = "contact_notes"
    __table_args__ = (Index("ix_contact_notes_attempt_created", "attempt_id", "created_at"),)

    id: Mapped[UUID] = uuid_column()
    attempt_id: Mapped[UUID] = mapped_column(ForeignKey("contact_attempts.id"))
    author_id: Mapped[UUID | None] = mapped_column(ForeignKey("staff_users.id"))
    text: Mapped[str] = mapped_column(Text)
    previous_revision_id: Mapped[UUID | None] = mapped_column(ForeignKey("contact_notes.id"))
    revision_reason: Mapped[str | None] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SheetAttempt(Base):
    __tablename__ = "sheet_attempts"

    id: Mapped[UUID] = uuid_column()
    sheet_id: Mapped[UUID] = mapped_column(ForeignKey("reception_sheets.id"))
    attempt_id: Mapped[UUID] = mapped_column(ForeignKey("contact_attempts.id"), unique=True)


class WorkScheduleVersion(Base):
    __tablename__ = "work_schedule_versions"
    __table_args__ = (
        UniqueConstraint("doctor_id", "effective_from", name="doctor_effective_from"),
        Index("ix_schedule_versions_doctor_effective", "doctor_id", "effective_from"),
    )

    id: Mapped[UUID] = uuid_column()
    doctor_id: Mapped[UUID] = mapped_column(ForeignKey("doctors.id"))
    effective_from: Mapped[date] = mapped_column(Date)
    weekly_intervals: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("staff_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DayOverride(Base):
    __tablename__ = "day_overrides"
    __table_args__ = (UniqueConstraint("doctor_id", "local_date", name="doctor_local_date"),)

    id: Mapped[UUID] = uuid_column()
    doctor_id: Mapped[UUID] = mapped_column(ForeignKey("doctors.id"))
    local_date: Mapped[date] = mapped_column(Date)
    intervals: Mapped[list[dict[str, str]]] = mapped_column(JSONB, default=list)
    closed: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str | None] = mapped_column(String(240))
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("staff_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ScheduleBlock(Base):
    __tablename__ = "schedule_blocks"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="positive_range"),
        Index("ix_schedule_blocks_doctor_start", "doctor_id", "start_at"),
    )

    id: Mapped[UUID] = uuid_column()
    doctor_id: Mapped[UUID] = mapped_column(ForeignKey("doctors.id"))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(240))
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("staff_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('scheduled','checked_in','completed','cancelled','no_show')",
            name="status",
        ),
        CheckConstraint("end_at > start_at", name="positive_duration"),
        ExcludeConstraint(
            ("doctor_id", "="),
            (func.tstzrange(text("start_at"), text("end_at"), "[)"), "&&"),
            where=text("status IN ('scheduled','checked_in')"),
            using="gist",
            name="excl_appointments_doctor_overlap",
        ),
        Index(
            "uq_appointments_inquiry_active",
            "inquiry_id",
            unique=True,
            postgresql_where=text("status IN ('scheduled','checked_in')"),
        ),
        Index("ix_appointments_doctor_start_status", "doctor_id", "start_at", "status"),
    )

    id: Mapped[UUID] = uuid_column()
    inquiry_id: Mapped[UUID] = mapped_column(ForeignKey("inquiries.id"))
    doctor_id: Mapped[UUID] = mapped_column(ForeignKey("doctors.id"))
    sheet_id: Mapped[UUID] = mapped_column(ForeignKey("reception_sheets.id"))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="scheduled")
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("staff_users.id"))
    schedule_version: Mapped[int] = mapped_column(Integer, default=1)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AppointmentEvent(Base):
    __tablename__ = "appointment_events"
    __table_args__ = (Index("ix_appointment_events_appointment", "appointment_id", "created_at"),)

    id: Mapped[UUID] = uuid_column()
    appointment_id: Mapped[UUID] = mapped_column(ForeignKey("appointments.id"))
    action: Mapped[str] = mapped_column(String(32))
    old_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    new_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    old_status: Mapped[str | None] = mapped_column(String(24))
    new_status: Mapped[str | None] = mapped_column(String(24))
    reason: Mapped[str | None] = mapped_column(String(500))
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("staff_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SettingsVersion(Base):
    __tablename__ = "settings_versions"
    __table_args__ = (UniqueConstraint("namespace", "version", name="namespace_version"),)

    id: Mapped[UUID] = uuid_column()
    namespace: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(16), default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("staff_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TelegramInbox(Base):
    __tablename__ = "telegram_inbox"
    __table_args__ = (
        UniqueConstraint("bot_id", "update_id", name="bot_update"),
        CheckConstraint("state IN ('pending','processing','completed','failed')", name="state"),
        Index("ix_telegram_inbox_state_lease", "state", "lease_until"),
    )

    id: Mapped[UUID] = uuid_column()
    bot_id: Mapped[int] = mapped_column(BigInteger)
    update_id: Mapped[int] = mapped_column(BigInteger)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(240))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OutboxJob(Base):
    __tablename__ = "outbox_jobs"
    __table_args__ = (
        CheckConstraint(
            "state IN ('pending','processing','sent','failed','cancelled')", name="state"
        ),
        Index("ix_outbox_state_due", "state", "due_at"),
    )

    id: Mapped[UUID] = uuid_column()
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True)
    kind: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[UUID | None] = mapped_column()
    bot_id: Mapped[int | None] = mapped_column(BigInteger)
    chat_id: Mapped[int | None] = mapped_column(BigInteger)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(16), default="pending")
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("actor_key", "route", "key", name="actor_route_key"),)

    id: Mapped[UUID] = uuid_column()
    actor_key: Mapped[str] = mapped_column(String(80))
    route: Mapped[str] = mapped_column(String(120))
    key: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_reference: Mapped[str] = mapped_column(String(120))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    worker_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_occurred_at", "occurred_at"),)

    id: Mapped[UUID] = uuid_column()
    actor_kind: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[str | None] = mapped_column(String(64), default=None)
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str | None] = mapped_column(String(64), default=None)
    request_id: Mapped[str] = mapped_column(String(64))
    source_key_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    changes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text, default=None)
