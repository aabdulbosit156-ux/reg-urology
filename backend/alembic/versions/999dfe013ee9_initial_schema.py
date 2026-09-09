"""initial schema

Revision ID: 999dfe013ee9
Revises:
Create Date: 2026-09-10 00:35:38.760859

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '999dfe013ee9'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

staff_role = postgresql.ENUM(
    "dev", "director", "admin", "analyst", name="staff_role", create_type=False
)
patient_status = postgresql.ENUM(
    "new",
    "scheduled",
    "unreachable",
    "advised",
    "no_show",
    "arrived",
    "analysis_ordered",
    "analysis_ready",
    name="patient_status",
    create_type=False,
)
patient_source = postgresql.ENUM(
    "bot", "manual", name="patient_source", create_type=False
)
staff_session_status = postgresql.ENUM(
    "pending", "confirmed", "expired", name="staff_session_status", create_type=False
)
appointment_status = postgresql.ENUM(
    "scheduled", "completed", "cancelled", name="appointment_status", create_type=False
)
analysis_uploaded_by = postgresql.ENUM(
    "patient", "staff", name="analysis_uploaded_by", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (
        staff_role,
        patient_status,
        patient_source,
        staff_session_status,
        appointment_status,
        analysis_uploaded_by,
    ):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "staff",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", staff_role, nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("login", sa.String(length=64), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_user_id"),
        sa.UniqueConstraint("login"),
    )

    op.create_table(
        "staff_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("role", staff_role, nullable=False),
        sa.Column("staff_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", staff_session_status, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index("ix_staff_sessions_token", "staff_sessions", ["token"])

    op.create_table(
        "patients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_username", sa.String(length=64), nullable=True),
        sa.Column("consultation_goal", sa.Text(), nullable=True),
        sa.Column("source", patient_source, nullable=False),
        sa.Column("status", patient_status, nullable=False),
        sa.Column("assigned_staff_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("invite_token", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assigned_staff_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_user_id"),
        sa.UniqueConstraint("invite_token"),
    )
    op.create_index("ix_patients_phone", "patients", ["phone"])
    op.create_index("ix_patients_status", "patients", ["status"])

    op.create_table(
        "status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_status", patient_status, nullable=True),
        sa.Column("to_status", patient_status, nullable=False),
        sa.Column("staff_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_status_history_patient_id", "status_history", ["patient_id"])

    op.create_table(
        "appointments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("staff_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("status", appointment_status, nullable=False),
        sa.Column("room", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_appointments_patient_id", "appointments", ["patient_id"])
    op.create_index("ix_appointments_start_at", "appointments", ["start_at"])

    op.create_table(
        "analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by", analysis_uploaded_by, nullable=False),
        sa.Column("uploaded_by_staff_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("telegram_file_id", sa.String(length=255), nullable=False),
        sa.Column("telegram_file_unique_id", sa.String(length=255), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("ordered", sa.Boolean(), nullable=False),
        sa.Column("ai_report", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_staff_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analyses_patient_id", "analyses", ["patient_id"])

    op.create_table(
        "clinic_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_token", sa.String(length=255), nullable=True),
        sa.Column("ai_token", sa.String(length=255), nullable=True),
        sa.Column("work_start", sa.Time(), nullable=True),
        sa.Column("work_end", sa.Time(), nullable=True),
        sa.Column("slot_minutes", sa.Integer(), nullable=False),
        sa.Column("bot_texts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("clinic_name", sa.String(length=255), nullable=True),
        sa.Column("clinic_lat", sa.Float(), nullable=True),
        sa.Column("clinic_lng", sa.Float(), nullable=True),
        sa.Column("clinic_contacts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "activity_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("staff_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("entity", sa.String(length=128), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("activity_log")
    op.drop_table("clinic_settings")
    op.drop_index("ix_analyses_patient_id", table_name="analyses")
    op.drop_table("analyses")
    op.drop_index("ix_appointments_start_at", table_name="appointments")
    op.drop_index("ix_appointments_patient_id", table_name="appointments")
    op.drop_table("appointments")
    op.drop_index("ix_status_history_patient_id", table_name="status_history")
    op.drop_table("status_history")
    op.drop_index("ix_patients_status", table_name="patients")
    op.drop_index("ix_patients_phone", table_name="patients")
    op.drop_table("patients")
    op.drop_index("ix_staff_sessions_token", table_name="staff_sessions")
    op.drop_table("staff_sessions")
    op.drop_table("staff")

    bind = op.get_bind()
    for enum in (
        analysis_uploaded_by,
        appointment_status,
        staff_session_status,
        patient_source,
        patient_status,
        staff_role,
    ):
        enum.drop(bind, checkfirst=True)
