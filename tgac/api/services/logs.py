"""Maintenance utilities for application logs and audit history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session

from ..models.core import AuditLog
from ..utils.event_log import JsonlEventLogger
from ..utils.settings import get_settings
from ..utils.time import utcnow


@dataclass(slots=True)
class LogPruneResult:
    """Container describing the outcome of a prune operation."""

    events_removed: int
    audit_removed: int
    cutoff: datetime

    def as_dict(self) -> dict[str, object]:
        return {
            "events_removed": self.events_removed,
            "audit_removed": self.audit_removed,
            "cutoff": self.cutoff,
        }


class LogMaintenanceService:
    """Prune JSONL event logs and audit entries according to retention policy."""

    def __init__(
        self,
        db: Session,
        *,
        events_path: str | Path | None = None,
        logger_factory: Callable[[Path], JsonlEventLogger] | None = None,
    ) -> None:
        self.db = db
        settings = get_settings()
        resolved_path = Path(events_path or settings.events_log_path)
        self.events_path = resolved_path
        self._logger_factory = logger_factory or JsonlEventLogger
        self._default_retention_days = settings.log_retention_days

    def prune(self, *, retention_days: int | None = None) -> LogPruneResult:
        """Prune log artifacts older than the retention window."""

        days = retention_days if retention_days is not None else self._default_retention_days
        days = max(days, 0)

        cutoff = utcnow() - timedelta(days=days)

        logger = self._logger_factory(self.events_path)
        events_removed = logger.prune(cutoff)

        audit_removed = (
            self.db.query(AuditLog).filter(AuditLog.ts < cutoff).delete(synchronize_session=False)
        )
        self.db.commit()

        return LogPruneResult(events_removed=events_removed, audit_removed=audit_removed, cutoff=cutoff)


__all__ = ["LogMaintenanceService", "LogPruneResult"]

