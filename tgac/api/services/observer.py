"""Utilities for comment visibility observation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Callable

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.core import Comment, CommentResult
from ..utils.time import utcnow

VisibilityProbe = Callable[[Comment], bool]


@dataclass
class ObserverService:
    """Encapsulate logic for verifying comment visibility state."""

    db: Session
    probe: VisibilityProbe
    stale_after: timedelta = timedelta(minutes=5)
    batch_size: int = 100

    def pending_comments(self) -> list[Comment]:
        """Return a batch of comments that require visibility checks."""

        threshold = utcnow() - self.stale_after
        query = (
            self.db.query(Comment)
            .filter(Comment.result == CommentResult.SUCCESS)
            .filter(
                or_(
                    Comment.visibility_checked_at.is_(None),
                    Comment.visibility_checked_at < threshold,
                )
            )
            .order_by(Comment.visibility_checked_at.is_(None).desc(), Comment.sent_at.asc(), Comment.id.asc())
        )
        if self.batch_size > 0:
            query = query.limit(self.batch_size)
        return query.all()

    def run_once(self) -> int:
        """Check visibility for pending comments and persist the results."""

        comments = self.pending_comments()
        if not comments:
            return 0

        now = utcnow()
        processed = 0
        for comment in comments:
            is_visible = self.probe(comment)
            comment.visible = bool(is_visible)
            comment.visibility_checked_at = now
            processed += 1

        self.db.commit()
        return processed


__all__ = ["ObserverService", "VisibilityProbe"]
