from datetime import time

from pydantic import BaseModel


class ScheduleSettingsOut(BaseModel):
    work_start: time
    work_end: time
    slot_minutes: int


class ScheduleSettingsUpdate(BaseModel):
    work_start: time
    work_end: time
    slot_minutes: int
