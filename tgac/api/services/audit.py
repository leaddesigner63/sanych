"""Service layer for interacting with audit log entries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from sqlalchemy.orm import Session

from ..models.core import AuditLog


class AuditLogServiceError(Exception):
    """Base error for audit log operations."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class InvalidLimit(AuditLogServiceError):
    """Raised when an invalid limit value is provided."""


@dataclass(slots=True)
class AuditLogWindow:
    """Result of a paginated audit log query."""

    items: list[AuditLog]
    next_cursor: int | None


@dataclass(slots=True)
class AuditLogService:
    """Encapsulates higher level audit log operations."""

    db: Session
    max_limit: int = 500

    def record(self, actor: str, action: str, meta: Mapping[str, object] | None = None) -> AuditLog:
        """Persist an audit log entry and return the stored model."""

        payload = dict(meta or {})
        entry = AuditLog(actor=actor, action=action, meta=payload)
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def list_recent(self, limit: int = 100, cursor: int | None = None) -> AuditLogWindow:
        """Return recent audit log entries ordered from newest to oldest."""

        if limit <= 0:
            raise InvalidLimit("Limit must be greater than zero", status_code=422)

        effective_limit = min(limit, self.max_limit)

        query = self.db.query(AuditLog).order_by(AuditLog.id.desc())
        if cursor is not None:
            query = query.filter(AuditLog.id < cursor)

        records: list[AuditLog] = query.limit(effective_limit + 1).all()
        has_more = len(records) > effective_limit
        items = records[:effective_limit]
        next_cursor = items[-1].id if has_more and items else None

        return AuditLogWindow(items=items, next_cursor=next_cursor)


__all__ = [
    "AuditLogService",
    "AuditLogServiceError",
    "AuditLogWindow",
    "InvalidLimit",
]

