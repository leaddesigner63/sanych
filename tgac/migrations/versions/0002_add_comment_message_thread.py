"""Add message and thread identifiers to comments.

Revision ID: 0002_add_comment_message_thread
Revises: 0001_initial
Create Date: 2025-10-16 00:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_add_comment_message_thread"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("comments", sa.Column("message_id", sa.Integer(), nullable=True))
    op.add_column("comments", sa.Column("thread_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("comments", "thread_id")
    op.drop_column("comments", "message_id")

