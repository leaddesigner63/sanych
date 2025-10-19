"""Pydantic models for dry-run simulation responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PreviewAssignmentSchema(BaseModel):
    task_id: int
    account_id: int


class PlanPreviewSchema(BaseModel):
    post_id: int
    channel_id: int
    telegram_post_id: int
    detected_at: datetime | None = None
    ready: list[PreviewAssignmentSchema]
    throttled: list[PreviewAssignmentSchema]
    pending_subscription: list[PreviewAssignmentSchema]


class DryRunResponse(BaseModel):
    items: list[PlanPreviewSchema]
    count: int


__all__ = [
    "DryRunResponse",
    "PlanPreviewSchema",
    "PreviewAssignmentSchema",
]
