from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy.orm import Session

from ..models.core import Job, JobStatus, JobType, Post, Task


class SchedulerCore:
    def __init__(self, db: Session):
        self.db = db

    def enqueue(self, job_type: JobType, payload: dict, run_after: datetime | None = None, priority: int = 0) -> Job:
        job = Job(type=job_type, payload=payload, run_after=run_after or datetime.utcnow(), priority=priority)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def plan_for_posts(self, posts: Iterable[Post]) -> int:
        count = 0
        for post in posts:
            self.enqueue(JobType.PLAN_COMMENTS, {"post_id": post.id})
            count += 1
        return count

    def pick_next_job(self, worker_id: str) -> Job | None:
        job = (
            self.db.query(Job)
            .filter(Job.status == JobStatus.PENDING, Job.run_after <= datetime.utcnow())
            .order_by(Job.priority.desc(), Job.id.asc())
            .first()
        )
        if job:
            job.status = JobStatus.RUNNING
            job.locked_by = worker_id
            job.locked_at = datetime.utcnow()
            self.db.commit()
        return job

    def release_job(self, job: Job, success: bool, error: str | None = None) -> None:
        job.status = JobStatus.DONE if success else JobStatus.FAILED
        job.last_error = error
        job.locked_by = None
        job.locked_at = None
        self.db.commit()


__all__ = ["SchedulerCore"]
