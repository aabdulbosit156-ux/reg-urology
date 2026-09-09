import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.staff import StaffRole


class StaffStatsOut(BaseModel):
    id: uuid.UUID
    full_name: str
    role: StaffRole
    phone: str | None
    is_active: bool
    patients_received: int
    created_at: datetime
