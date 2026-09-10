"""add login_tokens

Revision ID: 05cbcd6f602f
Revises: ce8bd779659d
Create Date: 2026-09-10 20:23:35.711072

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '05cbcd6f602f'
down_revision: str | Sequence[str] | None = 'ce8bd779659d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "login_tokens",
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("staff_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("token"),
    )


def downgrade() -> None:
    op.drop_table("login_tokens")
