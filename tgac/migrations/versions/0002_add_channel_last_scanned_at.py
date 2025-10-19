"""Add last_scanned_at column to channels"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_add_channel_last_scanned_at"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("channels", sa.Column("last_scanned_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("channels", "last_scanned_at")
