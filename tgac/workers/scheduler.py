from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from ..api.deps import SessionLocal, get_engine
from ..api.models.core import Post
from ..api.services.scheduler_core import SchedulerCore

logger = logging.getLogger(__name__)


def run_scheduler(poll_interval: int = 5) -> None:
    logger.info("Starting scheduler loop")
    while True:
        with SessionLocal(bind=get_engine()) as db:  # type: Session
            core = SchedulerCore(db)
            posts = db.query(Post).limit(10).all()
            planned_comments = core.plan_for_posts(posts)
            planned_health = core.plan_healthchecks()
            if planned_comments or planned_health:
                logger.info(
                    "Planned %s comment jobs and %s healthchecks",
                    planned_comments,
                    planned_health,
                )
        time.sleep(poll_interval)


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    run_scheduler()
