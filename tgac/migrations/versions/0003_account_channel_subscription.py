"""Add subscription tracking to account-channel mappings."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003_account_channel_subscription"
down_revision = "0002_comment_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "account_channel_map",
        sa.Column("is_subscribed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "account_channel_map",
        sa.Column("last_subscribed_at", sa.DateTime(), nullable=True),
    )
    op.alter_column("account_channel_map", "is_subscribed", server_default=None)


def downgrade() -> None:
    op.drop_column("account_channel_map", "last_subscribed_at")
    op.drop_column("account_channel_map", "is_subscribed")
