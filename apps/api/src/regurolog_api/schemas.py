from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from regurolog_api.contracts import AppointmentStatus, ContactAttemptOutcome, StaffRole


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BotTokenRequest(StrictModel):
    token: SecretStr = Field(min_length=20, max_length=256)
    confirm_replace: bool = False


class BotIdentityResponse(StrictModel):
    bot_id: int
    username: str
    display_name: str
    status: str


class BotConnectionResponse(BotIdentityResponse):
    last_update_at: datetime | None = None
    last_error: str | None = None


class InviteCreateRequest(StrictModel):
    role: Literal[StaffRole.DIRECTOR, StaffRole.ADMIN]


class InviteResponse(StrictModel):
    id: UUID
    role: StaffRole
    state: str
    expires_at: datetime
    claimed_full_name: str | None = None
    claimed_username: str | None = None
    deep_link: str | None = None
    qr_data_url: str | None = None


class StaffResponse(StrictModel):
    id: UUID
    telegram_user_id: int
    telegram_username: str | None
    full_name: str
    role: StaffRole
    state: str
    created_at: datetime


class LoginChallengeResponse(StrictModel):
    state: str
    matching_code: str
    expires_at: datetime
    deep_link: str | None = None
    qr_data_url: str | None = None


class CampaignCreateRequest(StrictModel):
    name: str = Field(min_length=2, max_length=120)
    utm_source: str = Field(min_length=1, max_length=120)
    utm_medium: str = Field(min_length=1, max_length=120)
    utm_campaign: str = Field(min_length=1, max_length=120)
    utm_content: str | None = Field(default=None, max_length=120)
    utm_term: str | None = Field(default=None, max_length=120)


class CampaignResponse(CampaignCreateRequest):
    id: UUID
    code: str
    deep_link: str | None = None
    qr_data_url: str | None = None
    archived_at: datetime | None
    revoked_at: datetime | None


class DoctorUpsertRequest(StrictModel):
    name: str = Field(min_length=2, max_length=120)
    clinic_address: str = Field(min_length=2, max_length=240)
    directions: str | None = Field(default=None, max_length=2000)
    contact_phone: str = Field(min_length=7, max_length=32)


class DoctorResponse(DoctorUpsertRequest):
    id: UUID
    timezone: Literal["Asia/Tashkent"]
    slot_minutes: int
    active: bool


class PatientListItem(StrictModel):
    id: UUID
    full_name: str
    phone_masked: str
    possible_duplicate: bool
    first_registered_at: datetime
    inquiry_id: UUID | None
    inquiry_status: str | None
    close_reason: str | None
    assigned_to_name: str | None
    ever_answered: bool
    appointment_status: str | None


class PatientListResponse(StrictModel):
    items: list[PatientListItem]
    total: int
    page: int
    page_size: int


class TimelineItem(StrictModel):
    kind: str
    title: str
    occurred_at: datetime
    detail: str | None = None


class PatientDetailResponse(StrictModel):
    id: UUID
    full_name: str
    phone_masked: str
    phone_e164: str | None = None
    telegram_user_id: int
    possible_duplicate: bool
    ever_answered: bool
    inquiry_id: UUID | None
    inquiry_status: str | None
    close_reason: str | None = None
    appointment_status: str | None = None
    reason: str | None
    assigned_to: UUID | None
    next_followup_at: datetime | None
    version: int | None
    timeline: list[TimelineItem]


class PatientUpdateRequest(StrictModel):
    full_name: str | None = None
    phone: str | None = None
    version: int


class InquiryAssignRequest(StrictModel):
    staff_id: UUID | None
    reason: str = Field(min_length=2, max_length=500)
    version: int


class InquiryCloseRequest(StrictModel):
    close_reason: Literal["attended", "declined", "unreachable", "duplicate", "cancelled", "other"]
    reason: str = Field(min_length=2, max_length=500)
    version: int


class InquiryReopenRequest(StrictModel):
    reason: str = Field(min_length=2, max_length=500)
    version: int


class InquiryResponse(StrictModel):
    id: UUID
    patient_id: UUID
    doctor_id: UUID
    status: str
    close_reason: str | None
    assigned_to: UUID | None
    reason: str | None
    registered_at: datetime
    next_followup_at: datetime | None
    version: int


class ContactAttemptStartResponse(StrictModel):
    id: UUID
    inquiry_id: UUID
    phone_e164: str
    outcome: ContactAttemptOutcome
    started_at: datetime
    lease_until: datetime
    sheet_id: UUID
    sheet_number: str


class ContactAttemptFinishRequest(StrictModel):
    outcome: Literal[
        ContactAttemptOutcome.ANSWERED,
        ContactAttemptOutcome.NO_ANSWER,
        ContactAttemptOutcome.BUSY,
        ContactAttemptOutcome.UNREACHABLE,
        ContactAttemptOutcome.WRONG_NUMBER,
        ContactAttemptOutcome.ABORTED,
    ]
    note: str | None = Field(default=None, max_length=4000)
    next_followup_at: datetime | None = None


class ContactAttemptResponse(StrictModel):
    id: UUID
    inquiry_id: UUID
    outcome: ContactAttemptOutcome
    started_at: datetime
    answered_at: datetime | None
    ended_at: datetime | None


class ContactNoteRequest(StrictModel):
    text: str = Field(min_length=1, max_length=4000)
    previous_revision_id: UUID | None = None
    revision_reason: str | None = Field(default=None, max_length=240)


class ReceptionSheetResponse(StrictModel):
    id: UUID
    number: str
    local_contact_date: date
    patient_name: str
    phone_e164: str
    timezone: Literal["Asia/Tashkent"] = "Asia/Tashkent"
    attempts: list[dict[str, Any]]
    appointments: list[dict[str, Any]]


class WeeklyScheduleRequest(StrictModel):
    doctor_id: UUID
    effective_from: date
    weekly_intervals: dict[str, list[dict[str, str]]]
    slot_minutes: int = Field(default=15, ge=5, le=240)


class WeeklyScheduleResponse(WeeklyScheduleRequest):
    id: UUID
    created_at: datetime


class DayOverrideRequest(StrictModel):
    doctor_id: UUID
    intervals: list[dict[str, str]] = Field(default_factory=list)
    closed: bool = False
    reason: str | None = Field(default=None, max_length=240)


class ScheduleBlockRequest(StrictModel):
    doctor_id: UUID
    start_at: datetime
    end_at: datetime
    reason: str = Field(min_length=2, max_length=240)


class AvailabilitySlot(StrictModel):
    start_at: datetime
    end_at: datetime
    available: bool
    state: str


class AvailabilityResponse(StrictModel):
    doctor_id: UUID
    local_date: date
    timezone: Literal["Asia/Tashkent"] = "Asia/Tashkent"
    configured: bool
    slots: list[AvailabilitySlot]


class CalendarDaySummary(StrictModel):
    local_date: date
    configured: bool
    total_slots: int
    available_slots: int
    blocked_slots: int
    scheduled: int
    checked_in: int
    completed: int
    no_show: int
    cancelled: int


class CalendarSummaryResponse(StrictModel):
    doctor_id: UUID
    date_from: date
    date_to: date
    timezone: Literal["Asia/Tashkent"] = "Asia/Tashkent"
    days: list[CalendarDaySummary]


class AppointmentCreateRequest(StrictModel):
    inquiry_id: UUID
    doctor_id: UUID
    start_at: datetime


class AppointmentRescheduleRequest(StrictModel):
    start_at: datetime
    version: int
    reason: str = Field(min_length=2, max_length=500)


class AppointmentTransitionRequest(StrictModel):
    status: AppointmentStatus
    version: int
    reason: str | None = Field(default=None, max_length=500)


class AppointmentCorrectionRequest(StrictModel):
    status: AppointmentStatus
    version: int
    reason: str = Field(min_length=2, max_length=500)


class AppointmentResponse(StrictModel):
    id: UUID
    inquiry_id: UUID
    doctor_id: UUID
    start_at: datetime
    end_at: datetime
    status: AppointmentStatus
    version: int
    outcome_pending: bool = False
    patient_name: str | None = None
    patient_phone: str | None = None
    telegram_user_id: int | None = None


class BookableInquiryResponse(StrictModel):
    """An open, answered inquiry that has no active appointment yet."""

    inquiry_id: UUID
    patient_name: str
    patient_phone: str
    registered_at: datetime
    reason: str | None = None


class SettingsDraftRequest(StrictModel):
    namespace: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,63}$")
    payload: dict[str, Any]


class SettingsVersionResponse(StrictModel):
    id: UUID
    namespace: str
    payload: dict[str, Any]
    version: int
    state: str
    published_at: datetime | None


class SettingsPublishRequest(StrictModel):
    version_id: UUID


class AnalyticsResponse(StrictModel):
    mode: str
    date_from: date
    date_to: date
    metrics: dict[str, int | float | None]
    daily: list[dict[str, Any]]
    breakdowns: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


class NoShowReportItem(StrictModel):
    appointment_id: UUID
    patient_name: str
    phone_masked: str
    operator_name: str | None
    start_at: datetime
    source: str
    rescheduled: bool


class WebhookResponse(StrictModel):
    accepted: bool
    duplicate: bool


class ActivityLogItem(StrictModel):
    id: UUID
    occurred_at: datetime
    actor_kind: str
    actor_name: str | None = None
    action: str
    entity_type: str
    note: str | None = None


class StaffActivityStat(StrictModel):
    staff_id: UUID
    full_name: str
    role: StaffRole
    state: str
    appointments_created: int
    actions: int


class AdminResetRequest(StrictModel):
    confirm: str = Field(min_length=1, max_length=64)
