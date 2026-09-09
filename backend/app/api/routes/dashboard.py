import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPrincipal, get_current_principal, get_db
from app.models.analysis import Analysis
from app.models.appointment import Appointment, AppointmentStatus
from app.models.patient import Patient, PatientStatus
from app.models.staff import StaffRole
from app.schemas.dashboard import DailyLeads, DashboardOut, StatusCounts
from app.schemas.patient import SEGMENT_STATUSES, PatientSegment

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

DAILY_LEADS_WINDOW_DAYS = 14


@router.get("", response_model=DashboardOut)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
) -> DashboardOut:
    if principal.role == StaffRole.analyst:
        in_progress_result = await db.execute(
            select(func.count())
            .select_from(Patient)
            .where(Patient.status.in_(SEGMENT_STATUSES[PatientSegment.in_progress]))
        )
        uploads_result = await db.execute(
            select(func.count())
            .select_from(Analysis)
            .where(Analysis.uploaded_by_staff_id == uuid.UUID(principal.sub))
        )
        return DashboardOut(
            segment_new=0,
            segment_in_progress=in_progress_result.scalar_one(),
            segment_unresponsive=0,
            appointments_today=0,
            analyses_pending=0,
            status_counts=StatusCounts(),
            daily_leads=[],
            my_analyses_uploaded=uploads_result.scalar_one(),
        )

    status_rows = await db.execute(select(Patient.status, func.count()).group_by(Patient.status))
    counts_by_status = dict(status_rows.all())
    status_counts = StatusCounts.from_counts(counts_by_status)

    segment_new = counts_by_status.get(PatientStatus.new, 0)
    segment_unresponsive = sum(
        counts_by_status.get(s, 0) for s in SEGMENT_STATUSES[PatientSegment.unresponsive]
    )
    segment_in_progress = sum(
        counts_by_status.get(s, 0) for s in SEGMENT_STATUSES[PatientSegment.in_progress]
    )

    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    appointments_today_result = await db.execute(
        select(func.count())
        .select_from(Appointment)
        .where(
            Appointment.status == AppointmentStatus.scheduled,
            Appointment.start_at >= today,
            Appointment.start_at < tomorrow,
        )
    )
    appointments_today = appointments_today_result.scalar_one()

    window_start = today - timedelta(days=DAILY_LEADS_WINDOW_DAYS - 1)
    leads_rows = await db.execute(
        select(func.date(Patient.created_at), func.count())
        .where(Patient.created_at >= window_start)
        .group_by(func.date(Patient.created_at))
    )
    leads_by_day = dict(leads_rows.all())
    daily_leads = [
        DailyLeads(
            date=(day := (window_start + timedelta(days=i)).date()),
            count=leads_by_day.get(day, 0),
        )
        for i in range(DAILY_LEADS_WINDOW_DAYS)
    ]

    return DashboardOut(
        segment_new=segment_new,
        segment_in_progress=segment_in_progress,
        segment_unresponsive=segment_unresponsive,
        appointments_today=appointments_today,
        analyses_pending=counts_by_status.get(PatientStatus.analysis_ordered, 0),
        status_counts=status_counts,
        daily_leads=daily_leads,
    )
