from dataclasses import dataclass
from typing import cast

from fastapi import Request

from regurolog_api.config import AppEnvironment, Settings
from regurolog_api.contracts import StaffRole
from regurolog_api.database import Database
from regurolog_api.errors import ApiError
from regurolog_api.models import Session, StaffUser
from regurolog_api.services.root_auth import RootAuthService
from regurolog_api.services.staff_auth import StaffAuthService

SESSION_COOKIE = "regurolog_session"
CSRF_COOKIE = "regurolog_csrf"
LOGIN_BINDING_COOKIE = "regurolog_login_binding"


@dataclass(frozen=True, slots=True)
class CurrentRoot:
    session: Session
    service: RootAuthService


@dataclass(frozen=True, slots=True)
class CurrentPrincipal:
    session: Session
    kind: str
    role: StaffRole
    staff: StaffUser | None
    service: RootAuthService | StaffAuthService

    @property
    def actor_id(self) -> str:
        return str(self.staff.id if self.staff else self.session.id)

    @property
    def actor_key(self) -> str:
        return f"{self.kind}:{self.actor_id}"


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
            # The public web proxy is the only caller of the private API. Use the
            # right-most value added by that trusted edge, not a client-spoofable
            # left-most X-Forwarded-For value.
            return forwarded.rsplit(",", 1)[-1].strip()[:128]
    return (request.client.host if request.client else "unknown")[:128]


def require_allowed_origin(request: Request, settings: Settings) -> None:
    origin = request.headers.get("origin")
    if origin is None:
        if settings.environment in {AppEnvironment.STAGING, AppEnvironment.PRODUCTION}:
            raise ApiError(403, "ORIGIN_REQUIRED", "So'rov manbasi tasdiqlanmadi")
        return
    normalized = origin.rstrip("/")
    if normalized in settings.allowed_origins:
        return
    # The trusted web proxy is the only caller of the private API and forwards the
    # public host the browser actually used. Accept a same-site origin without
    # needing PUBLIC_BASE_URL/ALLOWED_ORIGINS configured by hand.
    if settings.trust_proxy_headers:
        forwarded_host = request.headers.get("x-forwarded-host")
        if forwarded_host and normalized in {
            f"https://{forwarded_host}",
            f"http://{forwarded_host}",
        }:
            return
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


async def require_principal(request: Request) -> CurrentPrincipal:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise ApiError(401, "AUTH_REQUIRED", "Tizimga kirish talab qilinadi")

    settings = get_settings(request)
    database = get_database(request)
    root_service = root_auth_service(settings)
    staff_service = StaffAuthService(settings)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            root_session = await root_service.authenticate(db_session, token)
            if root_session is not None:
                return CurrentPrincipal(
                    session=root_session,
                    kind="root",
                    role=StaffRole.DEV,
                    staff=None,
                    service=root_service,
                )
            staff_result = await staff_service.authenticate(db_session, token)
            if staff_result is not None:
                staff_session, staff = staff_result
                return CurrentPrincipal(
                    session=staff_session,
                    kind="staff",
                    role=StaffRole(staff.role),
                    staff=staff,
                    service=staff_service,
                )
    raise ApiError(401, "SESSION_INVALID", "Sessiya tugagan yoki bekor qilingan")


def ensure_role(current: CurrentPrincipal, allowed: set[StaffRole]) -> None:
    if current.role not in allowed:
        raise ApiError(403, "FORBIDDEN", "Bu amal uchun ruxsat yetarli emas")


def require_csrf(request: Request, settings: Settings, current: CurrentPrincipal) -> None:
    require_allowed_origin(request, settings)
    csrf_token = request.headers.get("x-csrf-token")
    if not csrf_token or not current.service.csrf_matches(current.session, csrf_token):
        raise ApiError(403, "CSRF_INVALID", "Xavfsizlik tokeni noto'g'ri")
