"""Pydantic models for playlist endpoints."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class PlaylistCreateRequest(BaseModel):
    project_id: int = Field(default=1, ge=1)
    name: str
    desc: Optional[str] = None


class PlaylistUpdateRequest(BaseModel):
    name: Optional[str] = None
    desc: Optional[str] = None


class PlaylistAssignChannelsRequest(BaseModel):
    channel_ids: List[int]


__all__ = [
    "PlaylistCreateRequest",
    "PlaylistUpdateRequest",
    "PlaylistAssignChannelsRequest",
]
