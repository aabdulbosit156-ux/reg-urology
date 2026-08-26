from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from regurolog_api.api.dependencies import CurrentPrincipal, get_database, require_principal
from regurolog_api.contracts import HealthResponse, ReadinessResponse, StaffRole
from regurolog_api.database import Database
from regurolog_api.errors import ApiError
from regurolog_api.models import BotConnection, OutboxJob, TelegramInbox, WorkerHeartbeat

router = APIRouter()
DatabaseDependency = Annotated[Database, Depends(get_database)]
PrincipalDependency = Annotated[CurrentPrincipal, Depends(require_principal)]


@router.get(
    "/live",
    response_model=HealthResponse,
    summary="Process liveness",
)
async def live() -> HealthResponse:
    return HealthResponse()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {}},
    summary="Database readiness",
)
async def ready(database: DatabaseDependency) -> ReadinessResponse:
    try:
        await database.ping()
    except SQLAlchemyError as error:
        raise ApiError(503, "DATABASE_UNAVAILABLE", "Ma'lumotlar bazasi tayyor emas") from error
    return ReadinessResponse()


@router.get("/system")
async def system_health(
    current: PrincipalDependency,
    database: DatabaseDependency,
) -> dict[str, Any]:
    if current.role not in {StaffRole.DEV, StaffRole.DIRECTOR}:
        raise ApiError(403, "FORBIDDEN", "Tizim holati uchun ruxsat yetarli emas")
    now = datetime.now(UTC)
    async with database.session_factory() as db_session:
        heartbeat = await db_session.scalar(
            select(WorkerHeartbeat).order_by(WorkerHeartbeat.last_seen_at.desc()).limit(1)
        )
        pending_inbox = int(
            (
                await db_session.scalar(
                    select(func.count(TelegramInbox.id)).where(
                        TelegramInbox.state.in_(["pending", "processing"])
                    )
                )
            )
            or 0
        )
        pending_outbox = int(
            (
                await db_session.scalar(
                    select(func.count(OutboxJob.id)).where(
                        OutboxJob.state.in_(["pending", "processing"])
                    )
                )
            )
            or 0
        )
        bot_status = await db_session.scalar(
            select(BotConnection.status).where(BotConnection.active.is_(True)).limit(1)
        )
        bot_cleanup_required = int(
            (
                await db_session.scalar(
                    select(func.count(BotConnection.id)).where(
                        BotConnection.active.is_(False),
                        BotConnection.last_error == "OLD_WEBHOOK_CLEANUP_FAILED",
                    )
                )
            )
            or 0
        )
    worker_healthy = bool(heartbeat and heartbeat.last_seen_at >= now - timedelta(seconds=30))
    return {
        "status": "ok" if worker_healthy else "degraded",
        "database": "ok",
        "worker": "ok" if worker_healthy else "stale",
        "worker_last_seen_at": heartbeat.last_seen_at if heartbeat else None,
        "pending_inbox": pending_inbox,
        "pending_outbox": pending_outbox,
        "bot_status": str(bot_status) if bot_status is not None else "not_configured",
        "bot_cleanup_required": bot_cleanup_required,
    }
