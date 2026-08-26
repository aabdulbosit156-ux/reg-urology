from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from regurolog_api.models import OutboxJob


async def enqueue_telegram_message(
    db_session: AsyncSession,
    *,
    idempotency_key: str,
    bot_id: int,
    chat_id: int,
    text: str,
    reply_markup: dict[str, object] | None = None,
    entity_id: UUID | None = None,
    kind: str = "telegram_message",
    version: int = 1,
    due_at: datetime | None = None,
) -> None:
    payload: dict[str, object] = {"text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    now = datetime.now(UTC)
    await db_session.execute(
        insert(OutboxJob)
        .values(
            idempotency_key=idempotency_key,
            kind=kind,
            entity_id=entity_id,
            bot_id=bot_id,
            chat_id=chat_id,
            payload=payload,
            version=version,
            due_at=due_at or now,
            state="pending",
            attempts=0,
            created_at=now,
        )
        .on_conflict_do_nothing(index_elements=[OutboxJob.idempotency_key])
    )
