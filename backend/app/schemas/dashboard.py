from datetime import date

from pydantic import BaseModel

from app.models.patient import PatientStatus


class StatusCounts(BaseModel):
    new: int = 0
    scheduled: int = 0
    unreachable: int = 0
    advised: int = 0
    no_show: int = 0
    arrived: int = 0
    analysis_ordered: int = 0
    analysis_ready: int = 0

    @classmethod
    def from_counts(cls, counts: dict[PatientStatus, int]) -> "StatusCounts":
        return cls(**{status.value: counts.get(status, 0) for status in PatientStatus})


class DailyLeads(BaseModel):
    date: date
    count: int


class DashboardOut(BaseModel):
    segment_new: int
    segment_in_progress: int
    segment_unresponsive: int
    appointments_today: int
    analyses_pending: int
    status_counts: StatusCounts
    daily_leads: list[DailyLeads]
    my_analyses_uploaded: int | None = None
