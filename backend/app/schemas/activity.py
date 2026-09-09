import uuid
from datetime import datetime

from pydantic import BaseModel


class ActivityLogOut(BaseModel):
    id: uuid.UUID
    staff_id: uuid.UUID | None
    staff_name: str | None
    action: str
    entity: str | None
    entity_id: uuid.UUID | None
    meta: dict
    at: datetime


class ActivityLogListResponse(BaseModel):
    items: list[ActivityLogOut]
    total: int
