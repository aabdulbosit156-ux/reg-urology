from dataclasses import dataclass
from typing import cast

from fastapi import Request

from regurolog_api.config import AppEnvironment, Settings
from regurolog_api.database import Database
from regurolog_api.errors import ApiError
from regurolog_api.models import Session
from regurolog_api.services.root_auth import RootAuthService

SESSION_COOKIE = "regurolog_session"
CSRF_COOKIE = "regurolog_csrf"


@dataclass(frozen=True, slots=True)
class CurrentRoot:
    session: Session
    service: RootAuthService


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_database(request: Request) -> Database:
    database: Database | None = request.app.state.database
    if database is None:
        raise ApiError(503, "DATABASE_UNAVAILABLE", "Ma'lumotlar bazasi ulanmagan")
    return database


def root_auth_service(settings: Settings) -> RootAuthService:
    try:
        return RootAuthService(settings)
    except RuntimeError as error:
        raise ApiError(503, "ROOT_AUTH_NOT_CONFIGURED", "Root kirish hali sozlanmagan") from error


def request_source(request: Request, settings: Settings) -> str:
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()[:128]
    return (request.client.host if request.client else "unknown")[:128]


def require_allowed_origin(request: Request, settings: Settings) -> None:
    origin = request.headers.get("origin")
    if origin is None:
        if settings.environment in {AppEnvironment.STAGING, AppEnvironment.PRODUCTION}:
            raise ApiError(403, "ORIGIN_REQUIRED", "So'rov manbasi tasdiqlanmadi")
        return
    if origin.rstrip("/") not in settings.allowed_origins:
        raise ApiError(403, "ORIGIN_NOT_ALLOWED", "So'rov manbasi ruxsat etilmagan")


async def require_root(request: Request) -> CurrentRoot:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise ApiError(401, "AUTH_REQUIRED", "Tizimga kirish talab qilinadi")

    settings = get_settings(request)
    database = get_database(request)
    service = root_auth_service(settings)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            session = await service.authenticate(db_session, token)
    if session is None:
        raise ApiError(401, "SESSION_INVALID", "Sessiya tugagan yoki bekor qilingan")
    return CurrentRoot(session=session, service=service)
