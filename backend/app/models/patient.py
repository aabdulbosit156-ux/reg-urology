import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PatientStatus(StrEnum):
    new = "new"
    scheduled = "scheduled"
    unreachable = "unreachable"
    advised = "advised"
    no_show = "no_show"
    arrived = "arrived"
    analysis_ordered = "analysis_ordered"
    analysis_ready = "analysis_ready"


class PatientSource(StrEnum):
    bot = "bot"
    manual = "manual"


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    consultation_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[PatientSource] = mapped_column(
        SAEnum(PatientSource, name="patient_source"), default=PatientSource.bot, nullable=False
    )
    status: Mapped[PatientStatus] = mapped_column(
        SAEnum(PatientStatus, name="patient_status"),
        default=PatientStatus.new,
        nullable=False,
        index=True,
    )
    assigned_staff_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=True
    )
    invite_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
