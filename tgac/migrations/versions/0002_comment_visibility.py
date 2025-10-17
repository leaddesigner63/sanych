"""Add visibility tracking columns to comments table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_comment_visibility"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("comments", sa.Column("visible", sa.Boolean(), nullable=True))
    op.add_column("comments", sa.Column("visibility_checked_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("comments", "visibility_checked_at")
    op.drop_column("comments", "visible")
