from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from ..models.core import CommentResult


class HistoryEntry(BaseModel):
    """Representation of a single comment history item."""

    id: int
    account_id: int | None
    task_id: int | None
    channel_id: int | None
    post_id: int
    message_id: int | None = None
    thread_id: int | None = None
    result: CommentResult | None
    planned_at: datetime | None
    sent_at: datetime | None
    template: str | None = None
    rendered: str | None = None
    error_code: str | None = None
    error_msg: str | None = None
    visible: bool | None = None
    visibility_checked_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class HistoryResponse(BaseModel):
    """Envelope describing a collection of history entries."""

    items: list[HistoryEntry]
    count: int


__all__ = ["HistoryEntry", "HistoryResponse"]
