from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.core import (
    Comment,
    CommentResult,
    Job,
    JobStatus,
    JobType,
    Post,
)
from ..utils.time import utcnow
from ..utils.settings import get_settings


@dataclass
class SchedulerCore:
    db: Session
    comment_collision_limit: int | None = None

    def __post_init__(self) -> None:  # pragma: no cover - simple settings retrieval
        if self.comment_collision_limit is None:
            self.comment_collision_limit = get_settings().comment_collision_limit_per_post

    def enqueue(self, job_type: JobType, payload: dict, run_after: datetime | None = None, priority: int = 0) -> Job:
        job = Job(type=job_type, payload=payload, run_after=run_after or utcnow(), priority=priority)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def plan_for_posts(self, posts: Iterable[Post]) -> int:
        count = 0
        for post in posts:
            if self._should_skip_post(post):
                continue
            self.enqueue(JobType.PLAN_COMMENTS, {"post_id": post.id})
            count += 1
        return count

    def pick_next_job(self, worker_id: str) -> Job | None:
        job = (
            self.db.query(Job)
            .filter(Job.status == JobStatus.PENDING, Job.run_after <= utcnow())
            .order_by(Job.priority.desc(), Job.id.asc())
            .first()
        )
        if job:
            job.status = JobStatus.RUNNING
            job.locked_by = worker_id
            job.locked_at = utcnow()
            self.db.commit()
        return job

    def release_job(self, job: Job, success: bool, error: str | None = None) -> None:
        job.status = JobStatus.DONE if success else JobStatus.FAILED
        job.last_error = error
        job.locked_by = None
        job.locked_at = None
        self.db.commit()

    def _should_skip_post(self, post: Post) -> bool:
        limit = self.comment_collision_limit or 0
        if limit <= 0:
            return False
        return self._active_comment_slots(post) >= limit

    def _active_comment_slots(self, post: Post) -> int:
        limit = self.comment_collision_limit or 0
        if limit <= 0:
            return 0

        success_comments = (
            self.db.query(func.count(Comment.id))
            .filter(
                Comment.channel_id == post.channel_id,
                Comment.post_id == post.post_id,
                Comment.result == CommentResult.SUCCESS,
            )
            .scalar()
            or 0
        )

        active_statuses = (JobStatus.PENDING, JobStatus.RUNNING)
        pending_jobs = (
            self.db.query(func.count(Job.id))
            .filter(
                Job.type.in_([JobType.PLAN_COMMENTS, JobType.SEND_COMMENT]),
                Job.status.in_(active_statuses),
                Job.payload["post_id"].as_integer() == post.id,
            )
            .scalar()
            or 0
        )

        return success_comments + pending_jobs


__all__ = ["SchedulerCore"]
