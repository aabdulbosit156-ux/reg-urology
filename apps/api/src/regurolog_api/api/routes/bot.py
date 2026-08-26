import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from regurolog_api.api.dependencies import (
    CurrentPrincipal,
    ensure_role,
    get_database,
    get_settings,
    require_csrf,
    require_principal,
)
from regurolog_api.config import Settings
from regurolog_api.contracts import StaffRole
from regurolog_api.database import Database
from regurolog_api.errors import ApiError
from regurolog_api.models import BotConnection
from regurolog_api.schemas import BotConnectionResponse, BotIdentityResponse, BotTokenRequest
from regurolog_api.services.audit import add_audit
from regurolog_api.services.bot_connection import (
    BotConnectionError,
    BotConnectionService,
    BotReplacementRequired,
)

router = APIRouter()
logger = logging.getLogger(__name__)
SettingsDependency = Annotated[Settings, Depends(get_settings)]
DatabaseDependency = Annotated[Database, Depends(get_database)]
PrincipalDependency = Annotated[CurrentPrincipal, Depends(require_principal)]
BOT_ROLES = {StaffRole.DEV, StaffRole.DIRECTOR}


@router.get("", response_model=BotConnectionResponse | None)
async def bot_status(
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> BotConnectionResponse | None:
    ensure_role(current, BOT_ROLES)
    service = BotConnectionService(settings)
    async with database.session_factory() as db_session:
        connection = await service.active_connection(db_session)
    if connection is None:
        return None
    return BotConnectionResponse(
        bot_id=connection.bot_id,
        username=connection.username,
        display_name=connection.display_name,
        status=connection.status,
        last_update_at=connection.last_update_at,
        last_error=connection.last_error,
    )


@router.post("/validate", response_model=BotIdentityResponse)
async def validate_bot_token(
    payload: BotTokenRequest,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
) -> BotIdentityResponse:
    ensure_role(current, BOT_ROLES)
    require_csrf(request, settings, current)
    try:
        identity = await BotConnectionService(settings).validate(payload.token.get_secret_value())
    except (RuntimeError, BotConnectionError) as error:
        raise ApiError(422, "BOT_TOKEN_INVALID", "Telegram bot tokenini tasdiqlamadi") from error
    return BotIdentityResponse(
        bot_id=identity.bot_id,
        username=identity.username,
        display_name=identity.display_name,
        status="connecting",
    )


@router.post("/connect", response_model=BotConnectionResponse)
async def connect_bot(
    payload: BotTokenRequest,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> BotConnectionResponse:
    ensure_role(current, BOT_ROLES)
    require_csrf(request, settings, current)
    service = BotConnectionService(settings)
    try:
        async with database.session_factory() as db_session:
            async with db_session.begin():
                outcome = await service.connect(
                    db_session,
                    token=payload.token.get_secret_value(),
                    confirm_replace=payload.confirm_replace,
                )
                connection = outcome.connection
                add_audit(
                    db_session,
                    actor_kind=current.kind,
                    actor_id=current.actor_id,
                    action="bot.connected",
                    entity_type="bot_connection",
                    entity_id=connection.id,
                    request_id=request.state.request_id,
                    occurred_at=datetime.now(UTC),
                    changes={"bot_id": connection.bot_id, "username": connection.username},
                )
        if outcome.replaced_token and outcome.replaced_connection_id:
            try:
                await service.gateway.delete_webhook(outcome.replaced_token)
            except BotConnectionError:
                logger.warning(
                    "Old bot webhook cleanup failed; connection_id=%s",
                    outcome.replaced_connection_id,
                )
                async with database.session_factory() as cleanup_session:
                    async with cleanup_session.begin():
                        replaced = await cleanup_session.get(
                            BotConnection,
                            outcome.replaced_connection_id,
                            with_for_update=True,
                        )
                        if replaced is not None and not replaced.active:
                            replaced.status = "error"
                            replaced.last_error = "OLD_WEBHOOK_CLEANUP_FAILED"
                            replaced.updated_at = datetime.now(UTC)
    except BotReplacementRequired as error:
        raise ApiError(
            409,
            "BOT_REPLACEMENT_CONFIRMATION_REQUIRED",
            "Boshqa botga o‘tishni alohida tasdiqlang",
        ) from error
    except (RuntimeError, BotConnectionError) as error:
        raise ApiError(422, "BOT_CONNECTION_FAILED", str(error)) from error
    return BotConnectionResponse(
        bot_id=connection.bot_id,
        username=connection.username,
        display_name=connection.display_name,
        status=connection.status,
        last_update_at=connection.last_update_at,
        last_error=connection.last_error,
    )
