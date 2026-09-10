import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LoginToken(Base):
    """Short-lived token backing the 'log in via the bot' flow: the website mints one, the
    staff member confirms it by opening the bot deep link, then the website exchanges it for a
    session. Status is a plain string ("pending" | "confirmed" | "consumed")."""

    __tablename__ = "login_tokens"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    staff_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
