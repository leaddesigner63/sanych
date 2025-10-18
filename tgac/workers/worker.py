from __future__ import annotations

import logging
import time
import uuid

from sqlalchemy.orm import Session

from ..api.deps import SessionLocal, get_engine
from ..api.models.core import Job, JobType
from ..api.services.autoreg import AutoRegService, AutoRegServiceError, SmsActivateClient, SmsProviderError
from ..api.services.comment_engine import CommentEngine, CommentEngineError
from ..api.services.scheduler_core import SchedulerCore
from ..api.services.subscription import SubscriptionService
from ..api.utils.settings import get_settings

logger = logging.getLogger(__name__)


def process_job(core: SchedulerCore, job: Job, engine: CommentEngine | None = None) -> None:
    """Handle a single job by delegating to the appropriate service."""

    if engine is None:
        engine = CommentEngine(core.db)

    try:
        if job.type == JobType.PLAN_COMMENTS:
            post_id = job.payload.get("post_id")
            if post_id is None:
                raise ValueError("Job payload missing post_id")
            engine.plan_for_post(int(post_id))
            core.release_job(job, True)
        elif job.type == JobType.SEND_COMMENT:
            comment_id = job.payload.get("comment_id")
            if comment_id is None:
                raise ValueError("Job payload missing comment_id")
            result = engine.send_comment(int(comment_id))
            core.release_job(job, result.success, error=None if result.success else result.error_message)
        elif job.type == JobType.AUTOREG_STEP:
            settings = get_settings()
            if not settings.sms_activate_api_key:
                core.release_job(job, False, error="SMS Activate API key is not configured")
                return
            sms_client = SmsActivateClient(settings.sms_activate_api_key)
            autoreg = AutoRegService(core.db, core, sms_client)
            try:
                result = autoreg.process_job(job)
                core.release_job(job, result.success, error=result.error)
            finally:
                sms_client.close()
        elif job.type == JobType.SUBSCRIBE:
            service = SubscriptionService(core.db)
            result = service.process_job(job)
            core.release_job(job, result.success, error=result.error)
        else:
            core.release_job(job, False, error=f"Unsupported job type: {job.type}")
    except (CommentEngineError, AutoRegServiceError, SmsProviderError) as exc:
        logger.warning("Worker error for job %s: %s", job.id, exc)
        core.release_job(job, False, error=str(exc))
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Unhandled exception while processing job %s", job.id)
        core.release_job(job, False, error=str(exc))


def run_worker(poll_interval: int = 3) -> None:
    worker_id = f"worker-{uuid.uuid4()}"
    logger.info("Worker %s starting", worker_id)
    while True:
        with SessionLocal(bind=get_engine()) as db:  # type: Session
            core = SchedulerCore(db)
            job = core.pick_next_job(worker_id)
            if not job:
                time.sleep(poll_interval)
                continue
            logger.info("Processing job %s", job.id)
            process_job(core, job)
        time.sleep(0.1)


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    run_worker()
