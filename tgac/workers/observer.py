from __future__ import annotations

import logging
import time
from datetime import timedelta

from sqlalchemy.orm import Session

from ..api.deps import SessionLocal, get_engine
from ..api.models.core import Comment
from ..api.services.observer import ObserverService
from ..api.utils.settings import get_settings

logger = logging.getLogger(__name__)


def _default_probe(comment: Comment) -> bool:
    """Fallback probe that treats comments as visible until real checks exist."""

    logger.debug("Default probe used for comment %s", comment.id)
    return True


def run_observer(poll_interval: int = 30, batch_size: int = 100) -> None:
    logger.info("Observer loop started")
    settings = get_settings()
    stale_minutes = max(settings.comment_visibility_stale_minutes, 0)
    while True:
        with SessionLocal(bind=get_engine()) as db:  # type: Session
            service = ObserverService(
                db,
                probe=_default_probe,
                stale_after=timedelta(minutes=stale_minutes),
                batch_size=batch_size,
            )
            processed = service.run_once()
            if processed:
                logger.info("Checked visibility for %s comments", processed)
        time.sleep(poll_interval)


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    run_observer()
