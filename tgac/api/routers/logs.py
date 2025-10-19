from __future__ import annotations

from __future__ import annotations

from enum import Enum

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..deps import get_db
from ..schemas.common import DataResponse
from ..schemas import LogPruneResponse
from ..services.logs import LogMaintenanceService

router = APIRouter(prefix="/logs", tags=["logs"])


class LogSource(str, Enum):
    """Known log streams that can be tailed via the API."""

    APP = "app"
    EVENTS = "events"


_LOG_PATHS: dict[LogSource, str] = {
    LogSource.APP: "tgac/logs/app.log",
    LogSource.EVENTS: "tgac/logs/events.jsonl",
}


def _tail(path: str, lines: int) -> list[str]:
    """Return the last *lines* lines from *path* if it exists."""

    if lines <= 0:
        return []

    try:
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.readlines()
    except FileNotFoundError:
        return []

    if not content:
        return []
    return content[-lines:]


@router.get("/tail", response_model=DataResponse)
def tail_logs(
    lines: int = Query(200, ge=1, le=500),
    source: LogSource = LogSource.APP,
) -> DataResponse:
    path = _LOG_PATHS[source]
    content = _tail(path, lines)
    return DataResponse(data={"lines": content, "source": source.value})


@router.post("/prune", response_model=DataResponse)
def prune_logs(days: int | None = None, db: Session = Depends(get_db)) -> DataResponse:
    service = LogMaintenanceService(db)
    result = service.prune(retention_days=days)
    payload = LogPruneResponse(
        events_removed=result.events_removed,
        audit_removed=result.audit_removed,
        cutoff=result.cutoff,
    )
    return DataResponse(data=payload.model_dump(mode="json"))
