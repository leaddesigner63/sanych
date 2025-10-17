"""Utilities for writing operational events to JSONL logs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from ..models.core import Comment


def _isoformat(value: datetime | None) -> str | None:
    """Serialize datetime values to ISO 8601 strings."""

    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CommentEventLogger(Protocol):
    """Protocol describing comment-related event logging methods."""

    def comment_planned(self, comment: Comment) -> None:  # pragma: no cover - protocol
        ...

    def comment_sent(self, comment: Comment) -> None:  # pragma: no cover - protocol
        ...


@dataclass(slots=True)
class NullEventLogger:
    """No-op logger for tests and optional integrations."""

    def comment_planned(self, comment: Comment) -> None:  # pragma: no cover - trivial
        return

    def comment_sent(self, comment: Comment) -> None:  # pragma: no cover - trivial
        return


@dataclass(slots=True)
class JsonlEventLogger:
    """Persist events to a JSON Lines file."""

    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, payload: dict[str, Any]) -> None:
        record = {"timestamp": _now_iso(), **payload}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")

    def comment_planned(self, comment: Comment) -> None:
        self._write(
            {
                "type": "comment_planned",
                "comment_id": comment.id,
                "account_id": comment.account_id,
                "task_id": comment.task_id,
                "channel_id": comment.channel_id,
                "post_id": comment.post_id,
                "planned_at": _isoformat(comment.planned_at),
            }
        )

    def comment_sent(self, comment: Comment) -> None:
        result_value = comment.result.value if comment.result else None
        self._write(
            {
                "type": "comment_sent",
                "comment_id": comment.id,
                "account_id": comment.account_id,
                "task_id": comment.task_id,
                "channel_id": comment.channel_id,
                "post_id": comment.post_id,
                "result": result_value,
                "error_code": comment.error_code,
                "error_message": comment.error_msg,
                "sent_at": _isoformat(comment.sent_at),
                "planned_at": _isoformat(comment.planned_at),
            }
        )


__all__ = [
    "CommentEventLogger",
    "JsonlEventLogger",
    "NullEventLogger",
]

