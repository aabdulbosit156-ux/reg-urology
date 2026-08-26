from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from regurolog_api.models import AuditEvent


def add_audit(
    db_session: AsyncSession,
    *,
    actor_kind: str,
    actor_id: UUID | str | None,
    action: str,
    entity_type: str,
    entity_id: UUID | str | None,
    request_id: str,
    occurred_at: datetime,
    changes: dict[str, object] | None = None,
    note: str | None = None,
) -> None:
    db_session.add(
        AuditEvent(
            actor_kind=actor_kind,
            actor_id=str(actor_id) if actor_id else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            request_id=request_id,
            changes=changes or {},
            occurred_at=occurred_at,
            note=note,
        )
    )
