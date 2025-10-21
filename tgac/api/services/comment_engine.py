"""Business logic for planning and sending comments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.core import (
    Account,
    AccountChannelMap,
    AccountStatus,
    Channel,
    Comment,
    CommentResult,
    Job,
    JobStatus,
    JobType,
    Post,
    Task,
    TaskAssignment,
    TaskMode,
    TaskStatus,
)
from ..utils.event_log import CommentEventLogger, JsonlEventLogger
from ..utils.time import utcnow
from ..utils.settings import get_settings
from .throttle import AdaptiveThrottle

TemplateRenderer = Callable[[Task, Post, Account], str]


@dataclass(frozen=True, slots=True)
class SendResult:
    """Result of the comment sending pipeline."""

    result: CommentResult
    rendered: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    message_id: int | None = None
    thread_id: int | None = None

    @property
    def success(self) -> bool:
        return self.result == CommentResult.SUCCESS


SendCallback = Callable[[Comment], SendResult]


@dataclass(frozen=True, slots=True)
class PreviewAssignment:
    """Lightweight representation of an assignment selected during planning."""

    task_id: int
    account_id: int


@dataclass(frozen=True, slots=True)
class PlanPreview:
    """Summary of how the engine would act for a given post."""

    post_id: int
    channel_id: int
    telegram_post_id: int
    detected_at: datetime | None
    ready: list[PreviewAssignment]
    throttled: list[PreviewAssignment]
    pending_subscription: list[PreviewAssignment]


@dataclass(frozen=True, slots=True)
class _AssignmentCandidate:
    """Internal container holding task/account pairs during planning."""

    task: Task
    account: Account


class CommentEngineError(Exception):
    """Base exception for comment engine failures."""


class PostNotFound(CommentEngineError):
    """Raised when the target post does not exist."""


class CommentNotFound(CommentEngineError):
    """Raised when attempting to operate on a missing comment."""


@dataclass
class CommentEngine:
    """Plan and execute comment jobs for posts."""

    db: Session
    renderer: TemplateRenderer | None = None
    sender: SendCallback | None = None
    event_logger: CommentEventLogger | None = None
    throttler: AdaptiveThrottle | None = None
    max_active_threads_per_account: int | None = None

    def __post_init__(self) -> None:  # pragma: no cover - trivial defaults
        if self.renderer is None:
            self.renderer = self._default_renderer
        if self.sender is None:
            self.sender = self._default_sender
        if self.event_logger is None:
            settings = get_settings()
            self.event_logger = JsonlEventLogger(Path(settings.events_log_path))
        if self.throttler is None:
            self.throttler = AdaptiveThrottle(self.db)
        if self.max_active_threads_per_account is None:
            self.max_active_threads_per_account = get_settings().max_active_threads_per_account

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def plan_for_post(self, post_id: int) -> list[Comment]:
        """Generate comment tasks for the given post."""

        post = self.db.get(Post, post_id)
        if post is None:
            raise PostNotFound(f"Post {post_id} not found")

        channel = self.db.get(Channel, post.channel_id)
        if channel is None:
            raise PostNotFound(f"Channel {post.channel_id} for post {post_id} not found")

        candidates, pending = self._compute_candidates(post, channel)
        if not candidates and not pending:
            self.db.flush()
            return []

        subscribe_jobs_created = False
        for candidate in pending:
            job = self._ensure_subscription_job(candidate.account.id, channel.id, post)
            if job is not None:
                subscribe_jobs_created = True

        throttler = self.throttler or AdaptiveThrottle(self.db)
        allowed = throttler.allowed_for(channel.project_id, len(candidates))
        selected = candidates[:allowed]

        if not selected:
            if subscribe_jobs_created:
                self.db.commit()
            else:
                self.db.flush()
            return []

        now = utcnow()
        created: list[Comment] = []
        for candidate in selected:
            task = candidate.task
            account = candidate.account
            template = (task.config or {}).get("template") if task.config else None
            rendered = self.renderer(task, post, account)

            comment = Comment(
                account_id=account.id,
                task_id=task.id,
                channel_id=channel.id,
                post_id=post.post_id,
                template=template,
                rendered=rendered,
                planned_at=now,
            )
            self.db.add(comment)
            created.append(comment)

        self.db.flush()

        for comment in created:
            job = Job(type=JobType.SEND_COMMENT, payload={"comment_id": comment.id})
            self.db.add(job)

        self.db.commit()
        for comment in created:
            self.db.refresh(comment)

        for comment in created:
            self.event_logger.comment_planned(comment)

        return created

    def preview_for_post(self, post_id: int) -> PlanPreview:
        """Return a dry-run preview for how comments would be planned."""

        post = self.db.get(Post, post_id)
        if post is None:
            raise PostNotFound(f"Post {post_id} not found")

        channel = self.db.get(Channel, post.channel_id)
        if channel is None:
            raise PostNotFound(f"Channel {post.channel_id} for post {post_id} not found")

        candidates, pending = self._compute_candidates(post, channel)
        throttler = self.throttler or AdaptiveThrottle(self.db)
        allowed = throttler.allowed_for(channel.project_id, len(candidates))
        ready = candidates[:allowed]
        throttled = candidates[allowed:]

        return PlanPreview(
            post_id=post.id,
            channel_id=channel.id,
            telegram_post_id=post.post_id,
            detected_at=post.detected_at,
            ready=[
                PreviewAssignment(task_id=candidate.task.id, account_id=candidate.account.id)
                for candidate in ready
            ],
            throttled=[
                PreviewAssignment(task_id=candidate.task.id, account_id=candidate.account.id)
                for candidate in throttled
            ],
            pending_subscription=[
                PreviewAssignment(task_id=candidate.task.id, account_id=candidate.account.id)
                for candidate in pending
            ],
        )

    def _ensure_subscription_job(self, account_id: int, channel_id: int, post: Post) -> Job | None:
        """Create a subscription job if one is not already pending."""

        active_statuses = (JobStatus.PENDING, JobStatus.RUNNING)
        existing_job = (
            self.db.query(Job)
            .filter(
                Job.type == JobType.SUBSCRIBE,
                Job.status.in_(active_statuses),
                Job.payload["account_id"].as_integer() == account_id,
                Job.payload["channel_id"].as_integer() == channel_id,
            )
            .first()
        )
        if existing_job:
            return None

        job = Job(
            type=JobType.SUBSCRIBE,
            payload={
                "account_id": account_id,
                "channel_id": channel_id,
                "post_id": post.id,
            },
            priority=5,
        )
        self.db.add(job)
        return job

    def send_comment(self, comment_id: int) -> SendResult:
        """Execute the delivery for a prepared comment."""

        comment = self.db.get(Comment, comment_id)
        if comment is None:
            raise CommentNotFound(f"Comment {comment_id} not found")

        outcome = self.sender(comment)

        comment.sent_at = utcnow()
        comment.result = outcome.result
        if outcome.rendered is not None:
            comment.rendered = outcome.rendered
        comment.error_code = outcome.error_code
        comment.error_msg = outcome.error_message
        comment.message_id = outcome.message_id
        comment.thread_id = outcome.thread_id

        self.db.commit()
        self.db.refresh(comment)

        self.event_logger.comment_sent(comment)

        return outcome

    # ------------------------------------------------------------------
    # Default hooks
    # ------------------------------------------------------------------
    @staticmethod
    def _default_renderer(task: Task, post: Post, account: Account) -> str:
        template = (task.config or {}).get("template") if task.config else None
        if template:
            return template
        return f"Comment for post {post.post_id} by account {account.id}"

    @staticmethod
    def _default_sender(comment: Comment) -> SendResult:
        return SendResult(result=CommentResult.SUCCESS)

    def _compute_candidates(
        self, post: Post, channel: Channel
    ) -> tuple[list[_AssignmentCandidate], list[_AssignmentCandidate]]:
        tasks = (
            self.db.query(Task)
            .filter(
                Task.project_id == channel.project_id,
                Task.status == TaskStatus.ON,
                Task.mode == TaskMode.NEW_POSTS,
            )
            .all()
        )
        if not tasks:
            return [], []

        task_map = {task.id: task for task in tasks}
        assignments: Iterable[tuple[TaskAssignment, Account]] = (
            self.db.query(TaskAssignment, Account)
            .join(Account, TaskAssignment.account_id == Account.id)
            .filter(TaskAssignment.task_id.in_(task_map.keys()))
            .all()
        )
        assignments = list(assignments)
        if not assignments:
            return [], []

        channel_mappings = {
            mapping.account_id: mapping
            for mapping in (
                self.db.query(AccountChannelMap)
                .filter(AccountChannelMap.channel_id == channel.id)
                .all()
            )
        }

        candidate_account_ids = [account.id for _, account in assignments]
        existing_pairs = {
            account_id
            for (account_id,) in (
                self.db.query(Comment.account_id)
                .filter(
                    Comment.channel_id == channel.id,
                    Comment.post_id == post.post_id,
                    Comment.account_id.in_(candidate_account_ids),
                )
                .all()
            )
            if account_id is not None
        }

        max_threads = self.max_active_threads_per_account or 0
        if max_threads > 0 and candidate_account_ids:
            active_counts = dict(
                self.db.query(Comment.account_id, func.count())
                .filter(
                    Comment.account_id.in_(candidate_account_ids),
                    Comment.result.is_(None),
                )
                .group_by(Comment.account_id)
                .all()
            )
        else:
            active_counts = {}

        eligible: list[_AssignmentCandidate] = []
        pending_subscriptions: list[_AssignmentCandidate] = []

        for assignment, account in assignments:
            if account.status != AccountStatus.ACTIVE or account.is_paused:
                continue

            mapping = channel_mappings.get(account.id)
            if channel_mappings and mapping is None:
                continue

            if mapping is not None and not mapping.is_subscribed:
                task = task_map.get(assignment.task_id)
                if task is not None:
                    pending_subscriptions.append(_AssignmentCandidate(task=task, account=account))
                continue

            if account.id in existing_pairs:
                continue

            task = task_map.get(assignment.task_id)
            if task is None:
                continue

            if max_threads > 0:
                current_active = active_counts.get(account.id, 0)
                if current_active >= max_threads:
                    continue
                active_counts[account.id] = current_active + 1

            eligible.append(_AssignmentCandidate(task=task, account=account))

        return eligible, pending_subscriptions


__all__ = [
    "CommentEngine",
    "CommentEngineError",
    "PostNotFound",
    "CommentNotFound",
    "SendResult",
    "TemplateRenderer",
    "SendCallback",
    "PlanPreview",
    "PreviewAssignment",
]

