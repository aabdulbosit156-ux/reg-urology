import hmac
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from regurolog_api.api.dependencies import get_database, get_settings
from regurolog_api.config import Settings
from regurolog_api.database import Database
from regurolog_api.errors import ApiError
from regurolog_api.models import BotConnection, TelegramInbox
from regurolog_api.security import keyed_digest
from regurolog_api.services.bot_connection import BotConnectionService

router = APIRouter()
SettingsDependency = Annotated[Settings, Depends(get_settings)]
DatabaseDependency = Annotated[Database, Depends(get_database)]


@router.post("/webhook/{opaque_path}", status_code=204)
async def receive_update(
    opaque_path: str,
    payload: dict[str, Any],
    settings: SettingsDependency,
    database: DatabaseDependency,
    telegram_secret: Annotated[str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")] = None,
) -> None:
    """Persist a Telegram update before acknowledging delivery."""

    if len(opaque_path) < 24 or telegram_secret is None:
        raise ApiError(404, "WEBHOOK_NOT_FOUND", "Webhook topilmadi")
    try:
        service = BotConnectionService(settings)
    except RuntimeError as error:
        raise ApiError(503, "BOT_NOT_CONFIGURED", "Bot sozlanmagan") from error

    path_hash = service.webhook_path_hash(opaque_path)
    header_hash = keyed_digest("header:" + telegram_secret, service.webhook_secret)
    update_id = payload.get("update_id")
    if not isinstance(update_id, int) or isinstance(update_id, bool):
        raise ApiError(400, "INVALID_TELEGRAM_UPDATE", "Telegram update_id noto‘g‘ri")

    now = datetime.now(UTC)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            connection = await db_session.scalar(
                select(BotConnection)
                .where(
                    BotConnection.active.is_(True),
                    BotConnection.webhook_path_hash == path_hash,
                )
                .with_for_update()
            )
            if connection is None or not hmac.compare_digest(
                connection.webhook_secret_hash, header_hash
            ):
                raise ApiError(404, "WEBHOOK_NOT_FOUND", "Webhook topilmadi")
            await db_session.execute(
                insert(TelegramInbox)
                .values(
                    bot_id=connection.bot_id,
                    update_id=update_id,
                    payload=payload,
                    state="pending",
                    attempts=0,
                    received_at=now,
                )
                .on_conflict_do_nothing(constraint="bot_update")
            )
            connection.last_update_at = now
            connection.status = "connected"
            connection.last_error = None
            connection.updated_at = now
