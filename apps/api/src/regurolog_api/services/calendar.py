from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from regurolog_api.config import Settings
from regurolog_api.contracts import BUSINESS_TIMEZONE
from regurolog_api.domain.validation import (
    DomainValidationError,
    local_datetime_to_utc,
    parse_grid_time,
    validate_intervals,
)
from regurolog_api.errors import ApiError
from regurolog_api.models import (
    Appointment,
    Doctor,
    ScheduleBlock,
    WorkScheduleVersion,
)
from regurolog_api.schemas import AvailabilitySlot


class CalendarService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def lock_doctor(self, db_session: AsyncSession, doctor_id: UUID) -> Doctor:
        doctor = await db_session.scalar(
            select(Doctor).where(Doctor.id == doctor_id, Doctor.active.is_(True)).with_for_update()
        )
        if doctor is None:
            raise ApiError(404, "DOCTOR_NOT_FOUND", "Faol doktor topilmadi")
        return doctor

    async def slot_minutes(self, db_session: AsyncSession, doctor_id: UUID) -> int:
        value = await db_session.scalar(select(Doctor.slot_minutes).where(Doctor.id == doctor_id))
        return int(value) if value else 15

    async def intervals_for_date(
        self,
        db_session: AsyncSession,
        doctor_id: UUID,
        local_date: date,
        *,
        candidate_weekly: dict[str, list[dict[str, str]]] | None = None,
    ) -> tuple[list[dict[str, str]], WorkScheduleVersion | None]:
        if candidate_weekly is not None:
            return candidate_weekly.get(str(local_date.weekday()), []), None
        # Single current weekly schedule; no effective-from windows or day exceptions.
        version = await db_session.scalar(
            select(WorkScheduleVersion)
            .where(WorkScheduleVersion.doctor_id == doctor_id)
            .order_by(
                WorkScheduleVersion.effective_from.desc(),
                WorkScheduleVersion.created_at.desc(),
            )
            .limit(1)
        )
        if version is None:
            return [], None
        intervals = version.weekly_intervals.get(str(local_date.weekday()), [])
        return intervals if isinstance(intervals, list) else [], version

    async def availability(
        self, db_session: AsyncSession, doctor_id: UUID, local_date: date
    ) -> tuple[bool, list[AvailabilitySlot], WorkScheduleVersion | None]:
        minutes = await self.slot_minutes(db_session, doctor_id)
        intervals, version = await self.intervals_for_date(db_session, doctor_id, local_date)
        if not intervals:
            return version is not None, [], version
        day_start = local_datetime_to_utc(local_date, parse_grid_time("00:00"))
        day_end = day_start + timedelta(days=1)
        appointments = list(
            (
                await db_session.scalars(
                    select(Appointment).where(
                        Appointment.doctor_id == doctor_id,
                        Appointment.status.in_(["scheduled", "checked_in"]),
                        Appointment.start_at < day_end,
                        Appointment.end_at > day_start,
                    )
                )
            ).all()
        )
        blocks = list(
            (
                await db_session.scalars(
                    select(ScheduleBlock).where(
                        ScheduleBlock.doctor_id == doctor_id,
                        ScheduleBlock.start_at < day_end,
                        ScheduleBlock.end_at > day_start,
                    )
                )
            ).all()
        )
        now = datetime.now(UTC)
        slots: list[AvailabilitySlot] = []
        for interval in validate_intervals(intervals):
            cursor = local_datetime_to_utc(local_date, parse_grid_time(interval["start"]))
            interval_end = local_datetime_to_utc(local_date, parse_grid_time(interval["end"]))
            while cursor + timedelta(minutes=minutes) <= interval_end:
                end = cursor + timedelta(minutes=minutes)
                state = "available"
                if cursor <= now:
                    state = "past"
                elif any(item.start_at < end and item.end_at > cursor for item in appointments):
                    state = "occupied"
                elif any(item.start_at < end and item.end_at > cursor for item in blocks):
                    state = "blocked"
                slots.append(
                    AvailabilitySlot(
                        start_at=cursor,
                        end_at=end,
                        available=state == "available",
                        state=state,
                    )
                )
                cursor = end
        return True, slots, version

    async def ensure_slot_available(
        self,
        db_session: AsyncSession,
        doctor_id: UUID,
        start_at: datetime,
        *,
        exclude_appointment_id: UUID | None = None,
    ) -> WorkScheduleVersion | None:
        if start_at.tzinfo is None:
            raise ApiError(422, "TIMEZONE_REQUIRED", "Qabul vaqti timezone bilan yuborilsin")
        start_at = start_at.astimezone(UTC)
        local = start_at.astimezone(BUSINESS_TIMEZONE)
        # Exact slot alignment is enforced below by matching a generated slot.
        if local.second or local.microsecond:
            raise ApiError(422, "INVALID_SLOT_GRID", "Vaqt aniq slot chegarasida bo‘lsin")
        now = datetime.now(UTC)
        if start_at <= now:
            raise ApiError(422, "PAST_APPOINTMENT", "O‘tgan vaqtga qabul qo‘yib bo‘lmaydi")
        if start_at > now + timedelta(days=self.settings.booking_horizon_days):
            raise ApiError(422, "BOOKING_HORIZON", "Qabul bron ufqidan tashqarida")
        configured, slots, version = await self.availability(db_session, doctor_id, local.date())
        if not configured:
            raise ApiError(409, "SCHEDULE_NOT_CONFIGURED", "Bu kun uchun jadval sozlanmagan")
        slot = next((slot for slot in slots if slot.start_at == start_at), None)
        if slot is None:
            raise ApiError(422, "OUTSIDE_WORK_HOURS", "Vaqt ish jadvalidan tashqarida")
        if not slot.available:
            if exclude_appointment_id and slot.state == "occupied":
                occupant = await db_session.scalar(
                    select(Appointment).where(
                        Appointment.doctor_id == doctor_id,
                        Appointment.start_at == start_at,
                        Appointment.status.in_(["scheduled", "checked_in"]),
                    )
                )
                if occupant and occupant.id == exclude_appointment_id:
                    return version
            raise ApiError(409, "SLOT_TAKEN", "Bu vaqt hozirgina band qilindi")
        return version

    async def conflicting_appointments_for_weekly(
        self,
        db_session: AsyncSession,
        doctor_id: UUID,
        effective_from: date,
        weekly: dict[str, list[dict[str, str]]],
    ) -> list[UUID]:
        appointments = list(
            (
                await db_session.scalars(
                    select(Appointment).where(
                        Appointment.doctor_id == doctor_id,
                        Appointment.status.in_(["scheduled", "checked_in"]),
                        Appointment.start_at >= datetime.now(UTC),
                    )
                )
            ).all()
        )
        conflicts: list[UUID] = []
        for appointment in appointments:
            local_start = appointment.start_at.astimezone(BUSINESS_TIMEZONE)
            local_end = appointment.end_at.astimezone(BUSINESS_TIMEZONE)
            if local_start.date() < effective_from:
                continue
            intervals, _ = await self.intervals_for_date(
                db_session, doctor_id, local_start.date(), candidate_weekly=weekly
            )
            if not self._fits(intervals, local_start, local_end):
                conflicts.append(appointment.id)
        return conflicts

    @staticmethod
    def _fits(intervals: list[dict[str, str]], local_start: datetime, local_end: datetime) -> bool:
        for interval in validate_intervals(intervals):
            start = parse_grid_time(interval["start"])
            end = parse_grid_time(interval["end"])
            if (
                local_start.time().replace(tzinfo=None) >= start
                and local_end.time().replace(tzinfo=None) <= end
            ):
                return True
        return False


def domain_error_to_api(error: DomainValidationError) -> ApiError:
    return ApiError(422, "DOMAIN_VALIDATION_ERROR", error.message)
