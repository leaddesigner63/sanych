from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.core import Comment
from ..schemas.common import DataResponse
from ..schemas.history import HistoryEntry, HistoryResponse
from ..services.history import HistoryService, HistoryServiceError

router = APIRouter(prefix="/history", tags=["history"])


def _serialize_history(items: list[Comment]) -> dict:
    entries = [HistoryEntry.model_validate(item, from_attributes=True) for item in items]
    response = HistoryResponse(items=entries, count=len(entries))
    return response.model_dump(mode="json")


def _handle_error(exc: HistoryServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/account/{account_id}", response_model=DataResponse)
def account_history(
    account_id: int,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> DataResponse:
    service = HistoryService(db)
    try:
        comments = service.account_history(account_id, limit=limit)
    except HistoryServiceError as exc:  # pragma: no cover - converted by FastAPI
        raise _handle_error(exc)
    return DataResponse(data=_serialize_history(comments))


@router.get("/task/{task_id}", response_model=DataResponse)
def task_history(
    task_id: int,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> DataResponse:
    service = HistoryService(db)
    try:
        comments = service.task_history(task_id, limit=limit)
    except HistoryServiceError as exc:  # pragma: no cover - converted by FastAPI
        raise _handle_error(exc)
    return DataResponse(data=_serialize_history(comments))


__all__ = ["router"]
