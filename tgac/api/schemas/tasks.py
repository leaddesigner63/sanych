"""Pydantic schemas for task API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..models.core import TaskMode, TaskStatus


class TaskBase(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=255)
    mode: TaskMode = TaskMode.NEW_POSTS
    status: TaskStatus = TaskStatus.ON
    config: dict[str, Any] | None = None


class TaskCreateRequest(TaskBase):
    """Incoming payload for task creation."""


class TaskUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    mode: TaskMode | None = None
    status: TaskStatus | None = None
    config: dict[str, Any] | None = None


class TaskResponse(BaseModel):
    id: int
    project_id: int
    name: str
    mode: TaskMode
    status: TaskStatus
    config: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskAssignRequest(BaseModel):
    account_ids: list[int] = Field(default_factory=list)
    filters: dict[str, Any] | None = None


class TaskAssignResponse(BaseModel):
    task_id: int
    assigned: int
    already_linked: int
    skipped: int
    limit: int


class TaskStatsResponse(BaseModel):
    task_id: int
    assignments: int


__all__ = [
    "TaskBase",
    "TaskCreateRequest",
    "TaskUpdateRequest",
    "TaskResponse",
    "TaskAssignRequest",
    "TaskAssignResponse",
    "TaskStatsResponse",
]
