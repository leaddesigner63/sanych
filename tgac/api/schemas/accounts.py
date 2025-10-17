"""Pydantic models related to account operations."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field

from ..models.core import AccountStatus


class AssignProxyRequest(BaseModel):
    proxy_id: int


class AccountImportItem(BaseModel):
    phone: str
    status: AccountStatus | None = Field(default=None)
    tags: str | None = None
    notes: str | None = None


class AccountImportRequest(BaseModel):
    project_id: int
    accounts: list[AccountImportItem]


class AccountHealthcheckRequest(BaseModel):
    status: AccountStatus | None = None
    notes: str | None = None


class AccountHealthcheckResponse(BaseModel):
    id: int
    status: AccountStatus
    last_health_at: datetime
    notes: str | None = None


class AccountImportResponse(BaseModel):
    created: list[int]
    skipped: list[str]
    count: int


class AccountPauseResponse(BaseModel):
    id: int
    is_paused: bool


__all__ = [
    "AssignProxyRequest",
    "AccountImportItem",
    "AccountImportRequest",
    "AccountHealthcheckRequest",
    "AccountHealthcheckResponse",
    "AccountImportResponse",
    "AccountPauseResponse",
]
