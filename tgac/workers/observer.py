from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from ..api.deps import SessionLocal, get_engine
from ..api.models.core import Comment
from ..api.services.observer import ObserverService
from ..api.utils.event_log import CommentEventLogger, JsonlEventLogger
from ..api.utils.settings import get_settings

logger = logging.getLogger(__name__)


def _default_probe(comment: Comment) -> bool:
    """Fallback probe that treats comments as visible until real checks exist."""

    logger.debug("Default probe used for comment %s", comment.id)
    return True


def _session_factory() -> Session:
    return SessionLocal(bind=get_engine())


def process_once(
    *,
    probe: Callable[[Comment], bool] | None = None,
    stale_minutes: int | None = None,
    batch_size: int = 100,
    event_logger: CommentEventLogger | None = None,
    session_factory: Callable[[], Session] | None = None,
) -> int:
    """Execute a single observer cycle and return the number of processed comments."""

    if probe is None:
        probe = _default_probe

    settings = None
    if stale_minutes is None or event_logger is None:
        settings = get_settings()

    if stale_minutes is None:
        assert settings is not None  # for type-checkers
        stale_minutes = max(settings.comment_visibility_stale_minutes, 0)

    if event_logger is None:
        assert settings is not None
        event_logger = JsonlEventLogger(Path(settings.events_log_path))

    if session_factory is None:
        session_factory = _session_factory

    with session_factory() as db:
        service = ObserverService(
            db,
            probe=probe,
            stale_after=timedelta(minutes=stale_minutes),
            batch_size=batch_size,
            event_logger=event_logger,
        )
        return service.run_once()


def run_observer(poll_interval: int = 30, batch_size: int = 100) -> None:
    logger.info("Observer loop started")
    settings = get_settings()
    stale_minutes = max(settings.comment_visibility_stale_minutes, 0)
    event_logger = JsonlEventLogger(Path(settings.events_log_path))

    while True:
        processed = process_once(
            probe=_default_probe,
            stale_minutes=stale_minutes,
            batch_size=batch_size,
            event_logger=event_logger,
        )
        if processed:
            logger.info("Checked visibility for %s comments", processed)
        time.sleep(poll_interval)


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    run_observer()
