import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.models.patient import PatientSource, PatientStatus
from app.schemas.analysis import AnalysisOut
from app.schemas.appointment import AppointmentOut


class PatientSegment(StrEnum):
    new = "new"
    in_progress = "in_progress"
    unresponsive = "unresponsive"


SEGMENT_STATUSES: dict[PatientSegment, tuple[PatientStatus, ...]] = {
    PatientSegment.new: (PatientStatus.new,),
    PatientSegment.in_progress: (
        PatientStatus.scheduled,
        PatientStatus.advised,
        PatientStatus.arrived,
        PatientStatus.analysis_ordered,
        PatientStatus.analysis_ready,
    ),
    PatientSegment.unresponsive: (PatientStatus.unreachable, PatientStatus.no_show),
}


class PatientCreateRequest(BaseModel):
    full_name: str
    phone: str
    consultation_goal: str | None = None


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    phone: str
    telegram_user_id: int | None
    telegram_username: str | None
    consultation_goal: str | None
    source: PatientSource
    status: PatientStatus
    assigned_staff_id: uuid.UUID | None
    invite_deep_link: str | None
    created_at: datetime


class PatientListResponse(BaseModel):
    items: list[PatientOut]
    total: int


class StatusChangeRequest(BaseModel):
    to_status: PatientStatus
    note: str | None = None
    appointment_start_at: datetime | None = None
    appointment_duration_min: int | None = None


class StatusHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_status: PatientStatus | None
    to_status: PatientStatus
    staff_id: uuid.UUID | None
    staff_name: str | None
    note: str | None
    at: datetime


class PatientDetailResponse(PatientOut):
    history: list[StatusHistoryOut]
    appointments: list[AppointmentOut]
    analyses: list[AnalysisOut]
