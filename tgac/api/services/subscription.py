"""Subscription orchestration for ensuring accounts join channels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from ..models.core import AccountChannelMap, Job
from ..utils.time import utcnow


@dataclass(slots=True)
class SubscriptionResult:
    """Outcome of a subscription attempt."""

    success: bool
    error: str | None = None


class SubscriptionServiceError(Exception):
    """Base error for subscription issues."""


class SubscriptionService:
    """Handle subscription jobs for accounts and channels."""

    def __init__(
        self,
        db: Session,
        engine_factory: Callable[[Session], "CommentEngine"] | None = None,
    ) -> None:
        self.db = db
        self._engine_factory = engine_factory

    def process_job(self, job: Job) -> SubscriptionResult:
        payload = job.payload or {}
        account_id = payload.get("account_id")
        channel_id = payload.get("channel_id")
        if account_id is None or channel_id is None:
            return SubscriptionResult(False, "Job payload missing account_id or channel_id")

        mapping = (
            self.db.query(AccountChannelMap)
            .filter(
                AccountChannelMap.account_id == int(account_id),
                AccountChannelMap.channel_id == int(channel_id),
            )
            .one_or_none()
        )
        if mapping is None:
            return SubscriptionResult(False, "Account-channel mapping not found")

        now = utcnow()
        if not mapping.is_subscribed:
            mapping.is_subscribed = True
        mapping.last_subscribed_at = now
        self.db.commit()

        post_id = payload.get("post_id")
        if post_id is None:
            return SubscriptionResult(True)

        engine = self._get_engine()
        try:
            engine.plan_for_post(int(post_id))
        except Exception as exc:  # pragma: no cover - propagated to worker for handling
            return SubscriptionResult(False, str(exc))

        return SubscriptionResult(True)

    def _get_engine(self) -> "CommentEngine":
        if self._engine_factory is not None:
            return self._engine_factory(self.db)

        from .comment_engine import CommentEngine

        return CommentEngine(self.db)


__all__ = ["SubscriptionService", "SubscriptionResult", "SubscriptionServiceError"]
