from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, Enum as SAEnum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    telegram_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.USER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    quota_projects: Mapped[Optional[int]] = mapped_column(Integer)

    projects: Mapped[list["Project"]] = relationship(back_populates="owner")


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_project_user_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(SAEnum(ProjectStatus), default=ProjectStatus.ACTIVE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    owner: Mapped[User] = relationship(back_populates="projects")
    accounts: Mapped[list["Account"]] = relationship(back_populates="project")
    proxies: Mapped[list["Proxy"]] = relationship(back_populates="project")


class AccountStatus(str, Enum):
    NEEDS_LOGIN = "NEEDS_LOGIN"
    ACTIVE = "ACTIVE"
    BANNED = "BANNED"
    FLOOD_WAIT = "FLOOD_WAIT"
    DEAD = "DEAD"


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    session_enc: Mapped[bytes] = mapped_column(nullable=False)
    status: Mapped[AccountStatus] = mapped_column(SAEnum(AccountStatus), default=AccountStatus.NEEDS_LOGIN, nullable=False)
    proxy_id: Mapped[Optional[int]] = mapped_column(ForeignKey("proxies.id"))
    tags: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    last_health_at: Mapped[Optional[datetime]] = mapped_column()
    last_comment_at: Mapped[Optional[datetime]] = mapped_column()

    project: Mapped[Project] = relationship(back_populates="accounts")
    proxy: Mapped[Optional["Proxy"]] = relationship(back_populates="accounts")
    channels: Mapped[list["AccountChannelMap"]] = relationship(back_populates="account")


class ProxyScheme(str, Enum):
    HTTP = "http"
    SOCKS5 = "socks5"


class Proxy(Base, TimestampMixin):
    __tablename__ = "proxies"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_proxy_project_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    scheme: Mapped[ProxyScheme] = mapped_column(SAEnum(ProxyScheme), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(120))
    password: Mapped[Optional[str]] = mapped_column(String(120))
    last_check_at: Mapped[Optional[datetime]] = mapped_column()
    is_working: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    project: Mapped[Project] = relationship(back_populates="proxies")
    accounts: Mapped[list[Account]] = relationship(back_populates="proxy")


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    tg_id: Mapped[Optional[int]] = mapped_column(Integer)
    link: Mapped[Optional[str]] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    playlists: Mapped[list["PlaylistChannel"]] = relationship(back_populates="channel")


class Playlist(Base, TimestampMixin):
    __tablename__ = "playlists"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    desc: Mapped[Optional[str]] = mapped_column(Text)

    channels: Mapped[list["PlaylistChannel"]] = relationship(back_populates="playlist")


class PlaylistChannel(Base):
    __tablename__ = "playlists_channels"
    __table_args__ = (UniqueConstraint("playlist_id", "channel_id", name="uq_playlist_channel"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlists.id", ondelete="CASCADE"), nullable=False)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)

    playlist: Mapped[Playlist] = relationship(back_populates="channels")
    channel: Mapped[Channel] = relationship(back_populates="playlists")


class TaskStatus(str, Enum):
    ON = "ON"
    OFF = "OFF"
    PAUSED = "PAUSED"


class TaskMode(str, Enum):
    NEW_POSTS = "NEW_POSTS"


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(SAEnum(TaskStatus), default=TaskStatus.ON, nullable=False)
    mode: Mapped[TaskMode] = mapped_column(SAEnum(TaskMode), default=TaskMode.NEW_POSTS, nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class TaskAssignment(Base):
    __tablename__ = "task_assignments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    task: Mapped[Task] = relationship()
    account: Mapped[Account] = relationship()


class AccountChannelMap(Base):
    __tablename__ = "account_channel_map"
    __table_args__ = (UniqueConstraint("account_id", "channel_id", name="pk_account_channel"),)

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True)

    account: Mapped[Account] = relationship(back_populates="channels")


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (UniqueConstraint("channel_id", "post_id", name="uq_channel_post"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    post_id: Mapped[int] = mapped_column(Integer, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column()
    detected_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    state: Mapped[Optional[str]] = mapped_column(String(64))


class CommentResult(str, Enum):
    SUCCESS = "SUCCESS"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"))
    post_id: Mapped[int] = mapped_column(Integer, nullable=False)
    template: Mapped[Optional[str]] = mapped_column(Text)
    rendered: Mapped[Optional[str]] = mapped_column(Text)
    planned_at: Mapped[Optional[datetime]] = mapped_column()
    sent_at: Mapped[Optional[datetime]] = mapped_column()
    result: Mapped[Optional[CommentResult]] = mapped_column(SAEnum(CommentResult))
    error_code: Mapped[Optional[str]] = mapped_column(String(64))
    error_msg: Mapped[Optional[str]] = mapped_column(Text)


class JobType(str, Enum):
    SCAN_CHANNELS = "SCAN_CHANNELS"
    PLAN_COMMENTS = "PLAN_COMMENTS"
    SEND_COMMENT = "SEND_COMMENT"
    HEALTHCHECK = "HEALTHCHECK"
    AUTOREG_STEP = "AUTOREG_STEP"
    SUBSCRIBE = "SUBSCRIBE"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_status_run_after", "status", "run_after"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    type: Mapped[JobType] = mapped_column(SAEnum(JobType), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[JobStatus] = mapped_column(SAEnum(JobStatus), default=JobStatus.PENDING, nullable=False)
    run_after: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    locked_by: Mapped[Optional[str]] = mapped_column(String(64))
    locked_at: Mapped[Optional[datetime]] = mapped_column()
    tries: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text)


class Setting(Base):
    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("project_id", "key", name="pk_settings"),)

    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class LoginTokenStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"


class LoginToken(Base):
    __tablename__ = "login_tokens"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(64))
    chat_id: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[LoginTokenStatus] = mapped_column(SAEnum(LoginTokenStatus), default=LoginTokenStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column()


__all__ = [
    "User",
    "Project",
    "Account",
    "Proxy",
    "Channel",
    "Playlist",
    "PlaylistChannel",
    "Task",
    "TaskAssignment",
    "AccountChannelMap",
    "Post",
    "Comment",
    "Job",
    "Setting",
    "AuditLog",
    "LoginToken",
    "UserRole",
    "ProjectStatus",
    "AccountStatus",
    "ProxyScheme",
    "TaskStatus",
    "TaskMode",
    "CommentResult",
    "JobType",
    "JobStatus",
    "LoginTokenStatus",
]
