import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.staff import StaffRole


class StaffSessionStatus(StrEnum):
    pending = "pending"
    confirmed = "confirmed"
    expired = "expired"


class StaffSession(Base):
    __tablename__ = "staff_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    role: Mapped[StaffRole] = mapped_column(SAEnum(StaffRole, name="staff_role"), nullable=False)
    staff_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=True
    )
    status: Mapped[StaffSessionStatus] = mapped_column(
        SAEnum(StaffSessionStatus, name="staff_session_status"),
        default=StaffSessionStatus.pending,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
