from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_roles
from app.models.activity_log import ActivityLog
from app.models.staff import Staff, StaffRole
from app.schemas.activity import ActivityLogListResponse, ActivityLogOut

router = APIRouter(prefix="/activity", tags=["activity"])

VIEW_ROLES = (StaffRole.dev, StaffRole.director)


@router.get("", response_model=ActivityLogListResponse, dependencies=[Depends(require_roles(*VIEW_ROLES))])
async def list_activity(
    action: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ActivityLogListResponse:
    stmt = select(ActivityLog, Staff.full_name).outerjoin(Staff, ActivityLog.staff_id == Staff.id)
    if action:
        stmt = stmt.where(ActivityLog.action == action)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(ActivityLog.at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)

    items = [
        ActivityLogOut(
            id=log.id,
            staff_id=log.staff_id,
            staff_name=staff_name,
            action=log.action,
            entity=log.entity,
            entity_id=log.entity_id,
            meta=log.meta,
            at=log.at,
        )
        for log, staff_name in result.all()
    ]
    return ActivityLogListResponse(items=items, total=total)
