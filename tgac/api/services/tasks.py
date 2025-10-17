"""Task related business logic and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from sqlalchemy.orm import Session

from ..models.core import Account, Task, TaskAssignment

MAX_ASSIGNMENTS_PER_REQUEST = 50


class TaskServiceError(Exception):
    """Base class for task service errors."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class TaskNotFound(TaskServiceError):
    """Raised when a task cannot be located."""


class AccountNotFound(TaskServiceError):
    """Raised when one or more accounts do not exist."""


class ProjectMismatch(TaskServiceError):
    """Raised when entities belong to different projects."""


@dataclass
class AssignmentSummary:
    """Details about the performed assignment operation."""

    created: list[TaskAssignment]
    already_linked: int
    requested: int
    applied_limit: int

    @property
    def applied(self) -> int:
        return len(self.created)

    @property
    def skipped(self) -> int:
        return self.requested - self.applied - self.already_linked


@dataclass
class TaskService:
    """Encapsulates higher level operations around tasks."""

    db: Session
    max_assignments_per_request: int = MAX_ASSIGNMENTS_PER_REQUEST

    def _load_task(self, task_id: int) -> Task:
        task = self.db.get(Task, task_id)
        if task is None:
            raise TaskNotFound(f"Task {task_id} not found", status_code=404)
        return task

    def _load_accounts(self, account_ids: Iterable[int]) -> list[Account]:
        ids = list(account_ids)
        if not ids:
            return []
        accounts = self.db.query(Account).filter(Account.id.in_(ids)).all()
        existing = {account.id for account in accounts}
        missing = [account_id for account_id in ids if account_id not in existing]
        if missing:
            missing_str = ", ".join(str(mid) for mid in missing)
            raise AccountNotFound(f"Accounts not found: {missing_str}", status_code=404)
        return accounts

    def assign_accounts(self, task_id: int, account_ids: Sequence[int]) -> AssignmentSummary:
        """Assign accounts to a task respecting per-request limits."""

        task = self._load_task(task_id)
        unique_ids = list(dict.fromkeys(account_ids))
        if not unique_ids:
            return AssignmentSummary(created=[], already_linked=0, requested=0, applied_limit=self.max_assignments_per_request)

        accounts = self._load_accounts(unique_ids)

        for account in accounts:
            if account.project_id != task.project_id:
                raise ProjectMismatch("Task and accounts must belong to the same project")

        existing_assignments = (
            self.db.query(TaskAssignment)
            .filter(TaskAssignment.task_id == task_id, TaskAssignment.account_id.in_(unique_ids))
            .all()
        )
        already_linked = {assignment.account_id for assignment in existing_assignments}

        assignable_ids = [account.id for account in accounts if account.id not in already_linked]
        if not assignable_ids:
            self.db.flush()
            return AssignmentSummary(
                created=[],
                already_linked=len(already_linked),
                requested=len(unique_ids),
                applied_limit=self.max_assignments_per_request,
            )

        limited_ids = assignable_ids[: self.max_assignments_per_request]
        created: list[TaskAssignment] = []
        for account_id in limited_ids:
            mapping = TaskAssignment(task_id=task_id, account_id=account_id)
            self.db.add(mapping)
            created.append(mapping)

        if created:
            self.db.commit()
            for mapping in created:
                self.db.refresh(mapping)

        return AssignmentSummary(
            created=created,
            already_linked=len(already_linked),
            requested=len(unique_ids),
            applied_limit=self.max_assignments_per_request,
        )

    def stats(self, task_id: int) -> dict[str, int]:
        """Return simple statistics for the given task."""

        task = self._load_task(task_id)
        del task  # task existence validated
        total_assignments = self.db.query(TaskAssignment).filter(TaskAssignment.task_id == task_id).count()
        return {"assignments": total_assignments}


__all__ = [
    "TaskService",
    "TaskServiceError",
    "TaskNotFound",
    "AccountNotFound",
    "ProjectMismatch",
    "AssignmentSummary",
    "MAX_ASSIGNMENTS_PER_REQUEST",
]
