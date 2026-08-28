from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from regurolog_api.api.dependencies import (
    CSRF_COOKIE,
    LOGIN_BINDING_COOKIE,
    SESSION_COOKIE,
    CurrentPrincipal,
    get_database,
    get_settings,
    request_source,
    require_allowed_origin,
    require_csrf,
    require_principal,
    root_auth_service,
)
from regurolog_api.config import Settings
from regurolog_api.contracts import AuthPrincipal, AuthSessionResponse, RootLoginRequest
from regurolog_api.database import Database
from regurolog_api.errors import ApiError
from regurolog_api.models import AuditEvent, AuthThrottle
from regurolog_api.schemas import LoginChallengeResponse
from regurolog_api.services.audit import add_audit
from regurolog_api.services.root_auth import LoginFailure
from regurolog_api.services.staff_auth import StaffAuthService

router = APIRouter()
SettingsDependency = Annotated[Settings, Depends(get_settings)]
DatabaseDependency = Annotated[Database, Depends(get_database)]
CurrentPrincipalDependency = Annotated[CurrentPrincipal, Depends(require_principal)]


def _session_response(
    *,
    expires_at: datetime,
    csrf_token: str | None = None,
    principal: AuthPrincipal | None = None,
) -> AuthSessionResponse:
    return AuthSessionResponse(
        principal=principal or AuthPrincipal(),
        expires_at=expires_at,
        csrf_token=csrf_token,
    )


def _set_auth_cookies(
    response: Response,
    *,
    settings: Settings,
    session_token: str,
    csrf_token: str,
    max_age: int | None = None,
) -> None:
    cookie_max_age = max_age or settings.root_session_ttl_seconds
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        max_age=cookie_max_age,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=cookie_max_age,
        secure=settings.cookie_secure,
        httponly=False,
        samesite="lax",
        path="/",
    )


@router.post(
    "/root",
    response_model=AuthSessionResponse,
    responses={401: {}, 403: {}, 429: {}, 503: {}},
    summary="Create a short-lived root session",
)
async def root_login(
    payload: RootLoginRequest,
    request: Request,
    response: Response,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> AuthSessionResponse:
    require_allowed_origin(request, settings)
    service = root_auth_service(settings)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            result = await service.login(
                db_session,
                candidate=payload.token.get_secret_value(),
                source=request_source(request, settings),
                request_id=request.state.request_id,
            )

    if isinstance(result, LoginFailure):
        if result.code == "ROOT_LOGIN_RATE_LIMITED":
            retry_after = result.retry_after_seconds or settings.root_login_block_seconds
            raise ApiError(
                429,
                result.code,
                "Juda ko'p urinish. Birozdan keyin qayta urinib ko'ring",
                headers={"Retry-After": str(retry_after)},
            )
        raise ApiError(401, result.code, "Root token noto'g'ri")

    _set_auth_cookies(
        response,
        settings=settings,
        session_token=result.session_token,
        csrf_token=result.csrf_token,
    )
    response.headers["Cache-Control"] = "no-store"
    return _session_response(expires_at=result.session.expires_at, csrf_token=result.csrf_token)


@router.get(
    "/me",
    response_model=AuthSessionResponse,
    responses={401: {}, 503: {}},
    summary="Get current root session",
)
async def current_session(
    request: Request,
    response: Response,
    settings: SettingsDependency,
    current: CurrentPrincipalDependency,
) -> AuthSessionResponse:
    # Slide the browser cookies forward on every app load so an active operator
    # is not forced to log in again while the session itself keeps refreshing.
    session_token = request.cookies.get(SESSION_COOKIE)
    csrf_token = request.cookies.get(CSRF_COOKIE)
    if session_token and csrf_token:
        _set_auth_cookies(
            response,
            settings=settings,
            session_token=session_token,
            csrf_token=csrf_token,
            max_age=(
                settings.staff_session_ttl_seconds
                if current.kind == "staff"
                else settings.root_session_ttl_seconds
            ),
        )
    response.headers["Cache-Control"] = "no-store"
    return _session_response(
        expires_at=current.session.expires_at,
        principal=AuthPrincipal(
            kind="root" if current.kind == "root" else "staff",
            role=current.role,
            staff_id=str(current.staff.id) if current.staff else None,
            full_name=current.staff.full_name if current.staff else None,
        ),
    )


@router.post(
    "/logout",
    status_code=204,
    responses={401: {}, 403: {}, 503: {}},
    summary="Revoke the current root session",
)
async def logout(
    request: Request,
    response: Response,
    current: CurrentPrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> Response:
    require_csrf(request, settings, current)

    now = datetime.now(UTC)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            stored = await db_session.get(
                type(current.session), current.session.id, with_for_update=True
            )
            if stored and stored.revoked_at is None:
                stored.revoked_at = now
                db_session.add(
                    AuditEvent(
                        actor_kind=current.kind,
                        actor_id=current.actor_id,
                        action="auth.logout",
                        entity_type="session",
                        entity_id=str(stored.id),
                        request_id=request.state.request_id,
                        changes={},
                        occurred_at=now,
                    )
                )

    response.delete_cookie(SESSION_COOKIE, path="/", secure=settings.cookie_secure, httponly=True)
    response.delete_cookie(CSRF_COOKIE, path="/", secure=settings.cookie_secure)
    response.status_code = 204
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post(
    "/challenges",
    response_model=LoginChallengeResponse,
    status_code=201,
    summary="Create a browser-bound Telegram login challenge",
)
async def create_challenge(
    request: Request,
    response: Response,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> LoginChallengeResponse:
    require_allowed_origin(request, settings)
    service = StaffAuthService(settings)
    now = datetime.now(UTC)
    source_hash = service.digest("challenge-source", request_source(request, settings))
    async with database.session_factory() as db_session:
        async with db_session.begin():
            await db_session.execute(
                insert(AuthThrottle)
                .values(
                    key_hash=source_hash,
                    failure_count=0,
                    window_started_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing(index_elements=[AuthThrottle.key_hash])
            )
            throttle = await db_session.scalar(
                select(AuthThrottle).where(AuthThrottle.key_hash == source_hash).with_for_update()
            )
            if throttle is None:
                raise ApiError(503, "AUTH_THROTTLE_UNAVAILABLE", "Kirish himoyasi tayyor emas")
            if throttle.blocked_until and throttle.blocked_until > now:
                retry_after = max(1, int((throttle.blocked_until - now).total_seconds()))
                raise ApiError(
                    429,
                    "LOGIN_CHALLENGE_RATE_LIMITED",
                    "Juda ko‘p kirish so‘rovi. Birozdan keyin qayta urining",
                    headers={"Retry-After": str(retry_after)},
                )
            if now - throttle.window_started_at >= timedelta(
                seconds=settings.root_login_window_seconds
            ):
                throttle.failure_count = 0
                throttle.window_started_at = now
                throttle.blocked_until = None
            throttle.failure_count += 1
            throttle.updated_at = now
            if throttle.failure_count >= settings.root_login_max_attempts:
                throttle.blocked_until = now + timedelta(seconds=settings.root_login_block_seconds)
            try:
                created = await service.create_challenge(db_session)
            except RuntimeError as error:
                raise ApiError(409, "BOT_NOT_CONFIGURED", "Avval Telegram botni ulang") from error
            add_audit(
                db_session,
                actor_kind="anonymous",
                actor_id=None,
                action="auth.challenge_created",
                entity_type="auth_challenge",
                entity_id=created.challenge.id,
                request_id=request.state.request_id,
                occurred_at=datetime.now(UTC),
            )
    response.set_cookie(
        LOGIN_BINDING_COOKIE,
        created.browser_binding,
        max_age=settings.login_challenge_ttl_seconds,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
        path="/api/v1/auth",
    )
    response.headers["Cache-Control"] = "no-store"
    return LoginChallengeResponse(
        state=created.challenge.state,
        matching_code=created.challenge.matching_code,
        expires_at=created.challenge.expires_at,
        deep_link=created.deep_link,
        qr_data_url=created.qr_data_url,
    )


@router.get(
    "/challenges/current",
    response_model=LoginChallengeResponse,
    summary="Poll the browser-bound challenge without changing its state",
)
async def challenge_status(
    request: Request,
    response: Response,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> LoginChallengeResponse:
    binding = request.cookies.get(LOGIN_BINDING_COOKIE)
    if not binding:
        raise ApiError(404, "CHALLENGE_NOT_FOUND", "Kirish so‘rovi topilmadi")
    service = StaffAuthService(settings)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            challenge = await service.challenge_for_binding(db_session, binding)
    if challenge is None:
        raise ApiError(404, "CHALLENGE_NOT_FOUND", "Kirish so‘rovi topilmadi")
    response.headers["Cache-Control"] = "no-store"
    return LoginChallengeResponse(
        state=challenge.state,
        matching_code=challenge.matching_code,
        expires_at=challenge.expires_at,
    )


@router.post(
    "/exchange",
    response_model=AuthSessionResponse,
    summary="Atomically exchange an approved browser-bound challenge",
)
async def exchange_challenge(
    request: Request,
    response: Response,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> AuthSessionResponse:
    require_allowed_origin(request, settings)
    binding = request.cookies.get(LOGIN_BINDING_COOKIE)
    if not binding:
        raise ApiError(401, "BROWSER_BINDING_REQUIRED", "Kirish shu brauzerda boshlanishi kerak")
    service = StaffAuthService(settings)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            result = await service.exchange(db_session, binding)
            if result is not None:
                add_audit(
                    db_session,
                    actor_kind="staff",
                    actor_id=result.staff.id,
                    action="auth.exchange_succeeded",
                    entity_type="session",
                    entity_id=result.session.id,
                    request_id=request.state.request_id,
                    occurred_at=datetime.now(UTC),
                )
    if result is None:
        raise ApiError(409, "CHALLENGE_NOT_APPROVED", "Kirish hali tasdiqlanmagan yoki eskirgan")
    _set_auth_cookies(
        response,
        settings=settings,
        session_token=result.session_token,
        csrf_token=result.csrf_token,
        max_age=settings.staff_session_ttl_seconds,
    )
    response.delete_cookie(LOGIN_BINDING_COOKIE, path="/api/v1/auth")
    response.headers["Cache-Control"] = "no-store"
    return _session_response(
        expires_at=result.session.expires_at,
        csrf_token=result.csrf_token,
        principal=AuthPrincipal(
            kind="staff",
            role=result.staff.role,
            staff_id=str(result.staff.id),
            full_name=result.staff.full_name,
        ),
    )
