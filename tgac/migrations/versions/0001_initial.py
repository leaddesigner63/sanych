"""Initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2025-10-16 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite


# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False, unique=True),
        sa.Column("telegram_id", sa.Integer(), nullable=True, unique=True),
        sa.Column("role", sa.Enum("admin", "user", name="userrole"), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("quota_projects", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.Enum("active", "paused", "archived", name="projectstatus"), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "name", name="uq_project_user_name"),
    )

    op.create_table(
        "proxies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("scheme", sa.Enum("http", "socks5", name="proxyscheme"), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=120), nullable=True),
        sa.Column("password", sa.String(length=120), nullable=True),
        sa.Column("last_check_at", sa.DateTime(), nullable=True),
        sa.Column("is_working", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "name", name="uq_proxy_project_name"),
    )

    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False, unique=True),
        sa.Column("session_enc", sa.LargeBinary(), nullable=False),
        sa.Column("status", sa.Enum("NEEDS_LOGIN", "ACTIVE", "BANNED", "FLOOD_WAIT", "DEAD", name="accountstatus"), nullable=False, server_default="NEEDS_LOGIN"),
        sa.Column("proxy_id", sa.Integer(), sa.ForeignKey("proxies.id"), nullable=True),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("last_health_at", sa.DateTime(), nullable=True),
        sa.Column("last_comment_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("tg_id", sa.Integer(), nullable=True),
        sa.Column("link", sa.String(length=255), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "playlists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("desc", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "playlists_channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("playlist_id", sa.Integer(), sa.ForeignKey("playlists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("playlist_id", "channel_id", name="uq_playlist_channel"),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.Enum("ON", "OFF", "PAUSED", name="taskstatus"), nullable=False, server_default="ON"),
        sa.Column("mode", sa.Enum("NEW_POSTS", name="taskmode"), nullable=False, server_default="NEW_POSTS"),
        sa.Column("config", sqlite.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "task_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "account_channel_map",
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("detected_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("state", sa.String(length=64), nullable=True),
        sa.UniqueConstraint("channel_id", "post_id", name="uq_channel_post"),
    )

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="SET NULL")),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="SET NULL")),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("channels.id", ondelete="SET NULL")),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("template", sa.Text(), nullable=True),
        sa.Column("rendered", sa.Text(), nullable=True),
        sa.Column("planned_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("result", sa.Enum("SUCCESS", "SKIPPED", "ERROR", name="commentresult"), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_msg", sa.Text(), nullable=True),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type", sa.Enum("SCAN_CHANNELS", "PLAN_COMMENTS", "SEND_COMMENT", "HEALTHCHECK", "AUTOREG_STEP", "SUBSCRIBE", name="jobtype"), nullable=False),
        sa.Column("payload", sqlite.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Enum("PENDING", "RUNNING", "DONE", "FAILED", name="jobstatus"), nullable=False, server_default="PENDING"),
        sa.Column("run_after", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("locked_by", sa.String(length=64), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("tries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_jobs_status_run_after", "jobs", ["status", "run_after"])

    op.create_table(
        "settings",
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True, nullable=True),
        sa.Column("key", sa.String(length=120), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ts", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=255), nullable=False),
        sa.Column("meta", sqlite.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )

    op.create_table(
        "login_tokens",
        sa.Column("token", sa.String(length=64), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("chat_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.Enum("pending", "confirmed", "expired", name="logintokenstatus"), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("login_tokens")
    op.drop_table("audit_log")
    op.drop_table("settings")
    op.drop_index("ix_jobs_status_run_after", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("comments")
    op.drop_table("posts")
    op.drop_table("account_channel_map")
    op.drop_table("task_assignments")
    op.drop_table("tasks")
    op.drop_table("playlists_channels")
    op.drop_table("playlists")
    op.drop_table("channels")
    op.drop_table("accounts")
    op.drop_table("proxies")
    op.drop_table("projects")
    op.drop_table("users")
