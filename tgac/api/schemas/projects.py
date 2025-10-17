"""Pydantic models for project endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ..models.core import ProjectStatus


class ProjectCreateRequest(BaseModel):
    """Payload for creating a new project."""

    user_id: int = Field(..., ge=1)
    name: str = Field(..., min_length=1, max_length=120)
    status: ProjectStatus = ProjectStatus.ACTIVE


class ProjectUpdateRequest(BaseModel):
    """Partial update payload for an existing project."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    status: ProjectStatus | None = None


class ProjectResponse(BaseModel):
    """Representation of a project returned by the API."""

    id: int
    user_id: int
    name: str
    status: ProjectStatus
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


__all__ = [
    "ProjectCreateRequest",
    "ProjectUpdateRequest",
    "ProjectResponse",
]
