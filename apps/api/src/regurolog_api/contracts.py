from datetime import datetime
from enum import StrEnum
from typing import Final, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, SecretStr

BUSINESS_TIMEZONE_NAME: Final = "Asia/Tashkent"
BUSINESS_TIMEZONE: Final = ZoneInfo(BUSINESS_TIMEZONE_NAME)
APPOINTMENT_DURATION_MINUTES: Final = 15


class StaffRole(StrEnum):
    DEV = "DEV"
    DIRECTOR = "DIRECTOR"
    ADMIN = "ADMIN"


class InquiryStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class ContactAttemptOutcome(StrEnum):
    IN_PROGRESS = "in_progress"
    ANSWERED = "answered"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    UNREACHABLE = "unreachable"
    WRONG_NUMBER = "wrong_number"
    ABORTED = "aborted"
    INTERRUPTED = "interrupted"


class AppointmentStatus(StrEnum):
    SCHEDULED = "scheduled"
    CHECKED_IN = "checked_in"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class FieldError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    message: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    field_errors: list[FieldError] = Field(default_factory=list)
    request_id: str


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    service: Literal["regurolog-api"] = "regurolog-api"
    timezone: Literal["Asia/Tashkent"] = BUSINESS_TIMEZONE_NAME


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready"] = "ready"
    service: Literal["regurolog-api"] = "regurolog-api"
    database: Literal["ok"] = "ok"


class RootLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: SecretStr = Field(min_length=1, max_length=4096)


class AuthPrincipal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["root", "staff"] = "root"
    role: StaffRole = StaffRole.DEV
    staff_id: str | None = None
    full_name: str | None = None


class AuthSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    principal: AuthPrincipal = Field(default_factory=AuthPrincipal)
    expires_at: datetime
    csrf_token: str | None = None
