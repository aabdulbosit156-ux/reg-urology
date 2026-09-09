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


class AISettingsOut(BaseModel):
    ai_token_configured: bool


class AISettingsUpdate(BaseModel):
    ai_token: str


class BotSettingsOut(BaseModel):
    bot_token_configured: bool
    bot_username: str | None


class BotSettingsUpdate(BaseModel):
    bot_token: str


class BotTextsOut(BaseModel):
    texts: dict[str, str]


class BotTextsUpdate(BaseModel):
    texts: dict[str, str]


class ClinicProfileOut(BaseModel):
    clinic_name: str | None
    clinic_lat: float | None
    clinic_lng: float | None
    clinic_contacts: dict[str, str]


class ClinicProfileUpdate(BaseModel):
    clinic_name: str | None = None
    clinic_lat: float | None = None
    clinic_lng: float | None = None
    clinic_contacts: dict[str, str] = {}
