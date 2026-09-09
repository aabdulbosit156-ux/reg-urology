from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_roles
from app.models.patient import PatientStatus
from app.models.staff import Staff, StaffRole
from app.models.status_history import StatusHistory
from app.schemas.staff import StaffStatsOut

router = APIRouter(prefix="/staff", tags=["staff"])

MANAGE_ROLES = (StaffRole.dev, StaffRole.director, StaffRole.admin)


@router.get("", response_model=list[StaffStatsOut], dependencies=[Depends(require_roles(*MANAGE_ROLES))])
async def list_staff(db: AsyncSession = Depends(get_db)) -> list[StaffStatsOut]:
    received_rows = await db.execute(
        select(StatusHistory.staff_id, func.count(func.distinct(StatusHistory.patient_id)))
        .where(StatusHistory.to_status == PatientStatus.arrived, StatusHistory.staff_id.is_not(None))
        .group_by(StatusHistory.staff_id)
    )
    received_by_staff = dict(received_rows.all())

    staff_result = await db.execute(select(Staff).order_by(Staff.created_at))
    staff_list = staff_result.scalars().all()

    return [
        StaffStatsOut(
            id=staff.id,
            full_name=staff.full_name,
            role=staff.role,
            phone=staff.phone,
            is_active=staff.is_active,
            patients_received=received_by_staff.get(staff.id, 0),
            created_at=staff.created_at,
        )
        for staff in staff_list
    ]
