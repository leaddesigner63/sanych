from __future__ import annotations

import logging
import time
import uuid

from sqlalchemy.orm import Session

from ..api.deps import SessionLocal, get_engine
from ..api.models.core import JobStatus
from ..api.services.scheduler_core import SchedulerCore

logger = logging.getLogger(__name__)


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
            # TODO: implement actual job processing
            job.status = JobStatus.DONE
            db.commit()
        time.sleep(0.1)


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    run_worker()
