"""Create the RegUrolog V1 domain schema.

Revision ID: 20260826_0002
Revises: 20260826_0001
Create Date: 2026-08-26

The table list is intentionally explicit. The referenced SQLAlchemy tables are the V1 schema
snapshot and must not be removed; later changes require a new revision.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from regurolog_api import models  # noqa: F401
from regurolog_api.database import Base

revision: str = "20260826_0002"
down_revision: str | None = "20260826_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = (
    "staff_users",
    "staff_invites",
    "auth_challenges",
    "bot_connections",
    "bot_chat_bindings",
    "campaigns",
    "attribution_events",
    "patients",
    "doctors",
    "registration_drafts",
    "consents",
    "inquiries",
    "reception_sheets",
    "contact_attempts",
    "contact_notes",
    "sheet_attempts",
    "work_schedule_versions",
    "day_overrides",
    "schedule_blocks",
    "appointments",
    "appointment_events",
    "settings_versions",
    "telegram_inbox",
    "outbox_jobs",
    "idempotency_records",
    "worker_heartbeats",
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    bind = op.get_bind()

    # staff_users must exist before sessions can receive its staff principal FK.
    Base.metadata.tables["staff_users"].create(bind=bind, checkfirst=False)
    op.drop_constraint(op.f("ck_sessions_principal_type"), "sessions", type_="check")
    op.add_column("sessions", sa.Column("staff_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_sessions_staff_id_staff_users",
        "sessions",
        "staff_users",
        ["staff_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        "principal_type",
        "sessions",
        "principal_type IN ('root','staff')",
    )
    op.create_index("ix_sessions_staff_active", "sessions", ["staff_id", "revoked_at"])

    created = {"staff_users"}
    for table in Base.metadata.sorted_tables:
        if table.name in NEW_TABLES and table.name not in created:
            table.create(bind=bind, checkfirst=False)
            created.add(table.name)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in NEW_TABLES and table.name != "staff_users":
            table.drop(bind=bind, checkfirst=False)

    op.drop_index("ix_sessions_staff_active", table_name="sessions")
    op.drop_constraint(op.f("ck_sessions_principal_type"), "sessions", type_="check")
    op.drop_constraint("fk_sessions_staff_id_staff_users", "sessions", type_="foreignkey")
    op.drop_column("sessions", "staff_id")
    op.create_check_constraint(
        "principal_type",
        "sessions",
        "principal_type IN ('root')",
    )
    Base.metadata.tables["staff_users"].drop(bind=bind, checkfirst=False)
