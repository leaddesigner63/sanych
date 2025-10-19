"""Pydantic schemas for log maintenance endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LogPruneResponse(BaseModel):
    """API payload describing results of log pruning."""

    events_removed: int
    audit_removed: int
    cutoff: datetime


__all__ = ["LogPruneResponse"]

