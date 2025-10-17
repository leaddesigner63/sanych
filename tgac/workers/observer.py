from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from ..api.deps import SessionLocal, get_engine
from ..api.models.core import Comment

logger = logging.getLogger(__name__)


def run_observer(poll_interval: int = 30) -> None:
    logger.info("Observer loop started")
    while True:
        with SessionLocal(bind=get_engine()) as db:  # type: Session
            _ = db.query(Comment).count()
            logger.debug("Checked comment visibility stub")
        time.sleep(poll_interval)


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    run_observer()
