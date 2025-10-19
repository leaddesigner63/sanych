from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_db
from ..schemas.common import DataResponse
from ..schemas import LogPruneResponse
from ..services.logs import LogMaintenanceService

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/tail", response_model=DataResponse)
def tail_logs(lines: int = 200) -> DataResponse:
    path = "tgac/logs/app.log"
    try:
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.readlines()[-lines:]
    except FileNotFoundError:
        content = []
    return DataResponse(data={"lines": content})


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
