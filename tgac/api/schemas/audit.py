"""Pydantic models for audit log API payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditLogEntry(BaseModel):
    """Single audit log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ts: datetime
    actor: str
    action: str
    meta: dict[str, Any] = Field(default_factory=dict)


class AuditLogListResponse(BaseModel):
    """Response payload describing a window of audit log entries."""

    items: list[AuditLogEntry]
    count: int
    next_cursor: int | None = None


class AuditLogCreateRequest(BaseModel):
    """Request payload for recording a new audit log entry."""

    actor: str
    action: str
    meta: dict[str, Any] | None = None


__all__ = [
    "AuditLogCreateRequest",
    "AuditLogEntry",
    "AuditLogListResponse",
]

