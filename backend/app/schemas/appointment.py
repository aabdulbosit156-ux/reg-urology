import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.appointment import AppointmentStatus
from app.models.patient import PatientStatus


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    staff_id: uuid.UUID | None
    start_at: datetime
    duration_min: int
    status: AppointmentStatus
    room: str | None


class AppointmentPatientSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    phone: str
    status: PatientStatus


class CalendarAppointmentOut(AppointmentOut):
    patient: AppointmentPatientSummary


class AppointmentRescheduleRequest(BaseModel):
    start_at: datetime
