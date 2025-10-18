"""API endpoints for the audit log."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..deps import get_db
from ..schemas.audit import AuditLogCreateRequest, AuditLogEntry, AuditLogListResponse
from ..schemas.common import DataResponse
from ..services.audit import AuditLogService, AuditLogServiceError

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=DataResponse)
def list_audit_entries(
    limit: int = Query(100, ge=1, le=500),
    cursor: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
) -> DataResponse:
    """Return recent audit log entries with cursor-based pagination."""

    service = AuditLogService(db)
    limit_value = limit if isinstance(limit, int) else 100
    cursor_value = cursor if isinstance(cursor, int) else None
    try:
        window = service.list_recent(limit=limit_value, cursor=cursor_value)
    except AuditLogServiceError as exc:  # pragma: no cover - converted by FastAPI
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    items = [AuditLogEntry.model_validate(item, from_attributes=True) for item in window.items]
    response = AuditLogListResponse(items=items, count=len(items), next_cursor=window.next_cursor)
    return DataResponse(data=response.model_dump(mode="json"))


@router.post("", response_model=DataResponse)
def create_audit_entry(
    payload: AuditLogCreateRequest,
    db: Session = Depends(get_db),
) -> DataResponse:
    """Record a new audit log entry and return its representation."""

    service = AuditLogService(db)
    entry = service.record(payload.actor, payload.action, payload.meta or {})
    response = AuditLogEntry.model_validate(entry, from_attributes=True)
    return DataResponse(data=response.model_dump(mode="json"))


__all__ = ["router"]

