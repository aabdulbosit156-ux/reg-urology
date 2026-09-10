import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.staff import StaffRole

InvitableRole = Literal[StaffRole.director, StaffRole.admin, StaffRole.analyst]


class DevLoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: StaffRole
    expires_in: int


class StaffSessionCreateRequest(BaseModel):
    role: InvitableRole


class StaffSessionCreateResponse(BaseModel):
    token: str
    role: StaffRole
    deep_link: str
    expires_at: datetime


class StaffSessionConfirmRequest(BaseModel):
    token: str
    telegram_user_id: int
    full_name: str
    telegram_username: str | None = None
    phone: str | None = None


class StaffSessionConfirmResponse(BaseModel):
    staff_id: uuid.UUID
    role: StaffRole
    full_name: str


class MeResponse(BaseModel):
    sub: str
    role: StaffRole
    full_name: str | None = None


class StaffWebAppLoginRequest(BaseModel):
    init_data: str


class LoginTokenStartResponse(BaseModel):
    token: str
    deep_link: str
    expires_at: datetime


class LoginTokenStatusResponse(BaseModel):
    status: str  # "pending" | "confirmed" | "expired"
    access_token: str | None = None
    role: StaffRole | None = None
    expires_in: int | None = None
