"""Dry-run simulation helpers for comment planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from ..models.core import Channel, Post, Task
from .comment_engine import CommentEngine, PlanPreview


class SimulationServiceError(Exception):
    """Base error for dry-run simulation failures."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class TaskNotFound(SimulationServiceError):
    """Raised when attempting to simulate a non-existent task."""


class InvalidLimit(SimulationServiceError):
    """Raised when the requested preview window is invalid."""


@dataclass(slots=True)
class DryRunResult:
    """Single dry-run preview entry."""

    preview: PlanPreview


class SimulationService:
    """Provide dry-run previews for task comment planning."""

    def __init__(
        self,
        db: Session,
        engine_factory: Callable[[Session], CommentEngine] | None = None,
    ) -> None:
        self.db = db
        self._engine_factory = engine_factory

    def task_dry_run(self, task_id: int, *, limit: int = 5) -> list[DryRunResult]:
        """Return preview data for the latest posts associated with the task."""

        if limit <= 0:
            raise InvalidLimit("Limit must be greater than zero", status_code=422)

        task = self.db.get(Task, task_id)
        if task is None:
            raise TaskNotFound(f"Task {task_id} not found", status_code=404)

        posts = (
            self.db.query(Post)
            .join(Channel, Channel.id == Post.channel_id)
            .filter(Channel.project_id == task.project_id)
            .order_by(Post.detected_at.desc(), Post.id.desc())
            .limit(limit)
            .all()
        )
        if not posts:
            return []

        engine = self._engine_factory(self.db) if self._engine_factory else CommentEngine(self.db)

        results: list[DryRunResult] = []
        for post in posts:
            preview = engine.preview_for_post(post.id)
            results.append(DryRunResult(preview=preview))

        return results


__all__ = [
    "SimulationService",
    "SimulationServiceError",
    "DryRunResult",
    "TaskNotFound",
    "InvalidLimit",
]
