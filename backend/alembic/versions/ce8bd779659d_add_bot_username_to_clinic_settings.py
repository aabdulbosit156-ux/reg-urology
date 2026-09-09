"""add bot_username to clinic_settings

Revision ID: ce8bd779659d
Revises: 999dfe013ee9
Create Date: 2026-09-10 03:46:06.624334

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'ce8bd779659d'
down_revision: str | Sequence[str] | None = '999dfe013ee9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("clinic_settings", sa.Column("bot_username", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("clinic_settings", "bot_username")
