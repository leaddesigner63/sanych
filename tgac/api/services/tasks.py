"""Task related business logic and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from sqlalchemy.orm import Session

from ..models.core import Account, AccountStatus, Task, TaskAssignment

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


class InvalidFilter(TaskServiceError):
    """Raised when provided filters are not valid."""


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

    def assign_accounts(
        self,
        task_id: int,
        account_ids: Sequence[int] | None = None,
        filters: Mapping[str, object] | None = None,
    ) -> AssignmentSummary:
        """Assign accounts to a task respecting per-request limits."""

        task = self._load_task(task_id)
        candidate_ids = self._resolve_candidate_ids(task, account_ids, filters)
        unique_ids = list(dict.fromkeys(candidate_ids))
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _resolve_candidate_ids(
        self,
        task: Task,
        account_ids: Sequence[int] | None,
        filters: Mapping[str, object] | None,
    ) -> list[int]:
        result: list[int] = list(account_ids or [])
        if filters:
            result.extend(self._filter_account_ids(task, filters))
        return result

    def _filter_account_ids(self, task: Task, filters: Mapping[str, object]) -> list[int]:
        query = self.db.query(Account.id).filter(Account.project_id == task.project_id)

        status_filter = filters.get("status")
        if status_filter is not None:
            statuses = self._normalize_status_filter(status_filter)
            if not statuses:
                raise InvalidFilter("Status filter cannot be empty", status_code=422)
            query = query.filter(Account.status.in_(statuses))

        tags_filter = filters.get("tags")
        if tags_filter:
            tags = self._ensure_sequence(tags_filter)
            for tag in tags:
                if tag is None:
                    continue
                query = query.filter(Account.tags.ilike(f"%{str(tag)}%"))

        is_paused = filters.get("is_paused")
        if is_paused is not None:
            query = query.filter(Account.is_paused == bool(is_paused))

        exclude_ids = filters.get("exclude_ids")
        if exclude_ids:
            excluded = [int(account_id) for account_id in self._ensure_sequence(exclude_ids)]
            if excluded:
                query = query.filter(~Account.id.in_(excluded))

        limit_value = filters.get("limit")
        fetch_limit = self.max_assignments_per_request
        if limit_value is not None:
            try:
                limit_int = int(limit_value)
            except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
                raise InvalidFilter("Limit filter must be an integer", status_code=422) from exc
            if limit_int <= 0:
                raise InvalidFilter("Limit filter must be greater than zero", status_code=422)
            fetch_limit = min(limit_int, self.max_assignments_per_request)

        query = query.order_by(Account.id.asc())
        if fetch_limit:
            query = query.limit(fetch_limit)

        return [account_id for (account_id,) in query.all()]

    def _normalize_status_filter(self, raw: object) -> list[AccountStatus]:
        statuses = self._ensure_sequence(raw)
        normalized: list[AccountStatus] = []
        for item in statuses:
            if isinstance(item, AccountStatus):
                normalized.append(item)
                continue
            if isinstance(item, str):
                candidate = item
                try:
                    normalized.append(AccountStatus(candidate))
                    continue
                except ValueError:
                    pass
                try:
                    normalized.append(AccountStatus(candidate.upper()))
                    continue
                except ValueError as exc:
                    raise InvalidFilter(f"Unknown status filter: {item}", status_code=422) from exc
            else:  # pragma: no cover - defensive
                raise InvalidFilter("Status filter must be a string or AccountStatus", status_code=422)
        return normalized

    @staticmethod
    def _ensure_sequence(value: object) -> list[object]:
        if isinstance(value, (list, tuple, set)):
            return list(value)
        return [value]


__all__ = [
    "TaskService",
    "TaskServiceError",
    "TaskNotFound",
    "AccountNotFound",
    "ProjectMismatch",
    "InvalidFilter",
    "AssignmentSummary",
    "MAX_ASSIGNMENTS_PER_REQUEST",
]
