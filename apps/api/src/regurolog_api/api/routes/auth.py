from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from regurolog_api.api.dependencies import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    CurrentRoot,
    get_database,
    get_settings,
    request_source,
    require_allowed_origin,
    require_root,
    root_auth_service,
)
from regurolog_api.config import Settings
from regurolog_api.contracts import AuthSessionResponse, RootLoginRequest
from regurolog_api.database import Database
from regurolog_api.errors import ApiError
from regurolog_api.models import AuditEvent
from regurolog_api.services.root_auth import LoginFailure

router = APIRouter()
SettingsDependency = Annotated[Settings, Depends(get_settings)]
DatabaseDependency = Annotated[Database, Depends(get_database)]
CurrentRootDependency = Annotated[CurrentRoot, Depends(require_root)]


def _session_response(
    *, expires_at: datetime, csrf_token: str | None = None
) -> AuthSessionResponse:
    return AuthSessionResponse(expires_at=expires_at, csrf_token=csrf_token)


def _set_auth_cookies(
    response: Response,
    *,
    settings: Settings,
    session_token: str,
    csrf_token: str,
) -> None:
    max_age = settings.root_session_ttl_seconds
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        max_age=max_age,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=max_age,
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
    response: Response,
    current: CurrentRootDependency,
) -> AuthSessionResponse:
    response.headers["Cache-Control"] = "no-store"
    return _session_response(expires_at=current.session.expires_at)


@router.post(
    "/logout",
    status_code=204,
    responses={401: {}, 403: {}, 503: {}},
    summary="Revoke the current root session",
)
async def logout(
    request: Request,
    response: Response,
    current: CurrentRootDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> Response:
    require_allowed_origin(request, settings)
    csrf_token = request.headers.get("x-csrf-token")
    if not csrf_token or not current.service.csrf_matches(current.session, csrf_token):
        raise ApiError(403, "CSRF_INVALID", "Xavfsizlik tokeni noto'g'ri")

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
                        actor_kind="root",
                        actor_id=str(stored.id),
                        action="root.logout",
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
