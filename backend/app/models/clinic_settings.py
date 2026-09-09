from datetime import time

from sqlalchemy import Float, Integer, String, Time
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ClinicSettings(Base):
    """Single-row table (id is always 1) holding runtime-configurable clinic settings."""

    __tablename__ = "clinic_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    bot_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bot_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ai_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    work_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    work_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    slot_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    bot_texts: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    clinic_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    clinic_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    clinic_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    clinic_contacts: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
