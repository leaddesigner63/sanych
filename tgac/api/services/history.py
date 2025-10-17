from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.sql.elements import ColumnElement

from sqlalchemy.orm import Session

from ..models.core import Account, Comment, Task

DEFAULT_HISTORY_LIMIT = 100


class HistoryServiceError(Exception):
    """Base error class for the history service."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class AccountNotFound(HistoryServiceError):
    """Raised when an account cannot be located."""


class TaskNotFound(HistoryServiceError):
    """Raised when a task cannot be located."""


@dataclass
class HistoryService:
    """Provide access to comment history slices for accounts and tasks."""

    db: Session
    default_limit: int = DEFAULT_HISTORY_LIMIT

    def account_history(self, account_id: int, *, limit: int | None = None) -> list[Comment]:
        """Return the most recent comments for the given account."""

        self._ensure_account(account_id)
        return self._fetch_comments(Comment.account_id == account_id, limit)

    def task_history(self, task_id: int, *, limit: int | None = None) -> list[Comment]:
        """Return the most recent comments for the given task."""

        self._ensure_task(task_id)
        return self._fetch_comments(Comment.task_id == task_id, limit)

    def _fetch_comments(self, criterion: ColumnElement[bool], limit: int | None) -> list[Comment]:
        query = (
            self.db.query(Comment)
            .filter(criterion)
            .order_by(Comment.sent_at.desc(), Comment.id.desc())
        )
        final_limit = limit if limit is not None else self.default_limit
        if final_limit > 0:
            query = query.limit(final_limit)
        return query.all()

    def _ensure_account(self, account_id: int) -> Account:
        account = self.db.get(Account, account_id)
        if account is None:
            raise AccountNotFound(f"Account {account_id} not found", status_code=404)
        return account

    def _ensure_task(self, task_id: int) -> Task:
        task = self.db.get(Task, task_id)
        if task is None:
            raise TaskNotFound(f"Task {task_id} not found", status_code=404)
        return task


__all__ = [
    "HistoryService",
    "HistoryServiceError",
    "AccountNotFound",
    "TaskNotFound",
    "DEFAULT_HISTORY_LIMIT",
]
