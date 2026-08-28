"""Configurable appointment duration and a positive-duration check.

Revision ID: 20260828_0003
Revises: 20260826_0002
Create Date: 2026-08-28

Adds doctors.slot_minutes so the appointment length is configurable per doctor,
and replaces the hard-coded 15-minute appointment check with a generic
positive-duration check. Written with IF EXISTS / IF NOT EXISTS so it is safe to
re-run on container start.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260828_0003"
down_revision: str | None = "20260826_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE doctors ADD COLUMN IF NOT EXISTS slot_minutes INTEGER NOT NULL DEFAULT 15"
    )
    op.execute(
        "ALTER TABLE doctors DROP CONSTRAINT IF EXISTS ck_doctors_slot_minutes_range"
    )
    op.execute(
        "ALTER TABLE doctors ADD CONSTRAINT ck_doctors_slot_minutes_range "
        "CHECK (slot_minutes BETWEEN 5 AND 240)"
    )
    op.execute("ALTER TABLE appointments DROP CONSTRAINT IF EXISTS ck_appointments_duration_15m")
    op.execute(
        "ALTER TABLE appointments DROP CONSTRAINT IF EXISTS ck_appointments_positive_duration"
    )
    op.execute(
        "ALTER TABLE appointments ADD CONSTRAINT ck_appointments_positive_duration "
        "CHECK (end_at > start_at)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE appointments DROP CONSTRAINT IF EXISTS ck_appointments_positive_duration"
    )
    op.execute(
        "ALTER TABLE appointments ADD CONSTRAINT ck_appointments_duration_15m "
        "CHECK (end_at = start_at + interval '15 minutes')"
    )
    op.execute("ALTER TABLE doctors DROP CONSTRAINT IF EXISTS ck_doctors_slot_minutes_range")
    op.execute("ALTER TABLE doctors DROP COLUMN IF EXISTS slot_minutes")
