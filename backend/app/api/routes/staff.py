import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPrincipal, get_db, require_roles, staff_id_or_none
from app.models.activity_log import ActivityLog
from app.models.patient import PatientStatus
from app.models.staff import Staff, StaffRole
from app.models.status_history import StatusHistory
from app.schemas.staff import StaffStatsOut, StaffUpdateRequest

router = APIRouter(prefix="/staff", tags=["staff"])

MANAGE_ROLES = (StaffRole.dev, StaffRole.director, StaffRole.admin)
# Only dev/director may enable or revoke a staff member's access.
DEACTIVATE_ROLES = (StaffRole.dev, StaffRole.director)


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


@router.patch("/{staff_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_staff_access(
    staff_id: uuid.UUID,
    payload: StaffUpdateRequest,
    db: AsyncSession = Depends(get_db),
    principal: CurrentPrincipal = Depends(require_roles(*DEACTIVATE_ROLES)),
) -> None:
    """Enable/revoke a staff member's access. This is a soft action — it only flips is_active,
    so all of their history (status changes, uploaded analyses, appointments) is preserved."""
    if staff_id_or_none(principal) == staff_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "O'zingizni o'chira olmaysiz")

    result = await db.execute(select(Staff).where(Staff.id == staff_id))
    staff = result.scalar_one_or_none()
    if staff is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Xodim topilmadi")

    staff.is_active = payload.is_active
    db.add(
        ActivityLog(
            staff_id=staff_id_or_none(principal),
            action="staff.activate" if payload.is_active else "staff.deactivate",
            entity="staff",
            entity_id=staff.id,
            meta={"full_name": staff.full_name, "role": staff.role.value},
        )
    )
    await db.commit()
