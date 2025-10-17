"""Pydantic models for channel endpoints."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ChannelCreate(BaseModel):
    project_id: int = Field(default=1, ge=1)
    title: str
    username: Optional[str] = None
    tg_id: Optional[int] = Field(default=None, ge=0)
    link: Optional[str] = None
    active: bool = True


class ChannelImportItem(ChannelCreate):
    pass


class ChannelImportRequest(BaseModel):
    channels: List[ChannelImportItem]


class ChannelAssignAccountsRequest(BaseModel):
    account_ids: List[int]


__all__ = [
    "ChannelCreate",
    "ChannelImportRequest",
    "ChannelAssignAccountsRequest",
]
