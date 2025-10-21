"""Business logic helpers for project management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.core import Project, ProjectStatus, User
from ..utils.settings import Settings, get_settings


class ProjectServiceError(Exception):
    """Base error for project operations."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class UserNotFound(ProjectServiceError):
    """Raised when the project owner does not exist."""

    def __init__(self, user_id: int) -> None:
        super().__init__(f"User {user_id} not found", status_code=404)


class ProjectQuotaExceeded(ProjectServiceError):
    """Raised when a user has reached their project limit."""

    def __init__(self, user: User, quota: int) -> None:
        message = (
            f"User {user.username} has reached the project quota ({quota})"
        )
        super().__init__(message, status_code=403)
        self.user = user
        self.quota = quota


@dataclass(slots=True)
class ProjectService:
    """Encapsulate project creation rules such as per-user quotas."""

    db: Session
    settings: Settings | None = None

    def __post_init__(self) -> None:  # pragma: no cover - simple default wiring
        if self.settings is None:
            self.settings = get_settings()

    def create_project(
        self, *, user_id: int, name: str, status: ProjectStatus
    ) -> Project:
        """Create a project for the given user respecting quotas."""

        user = self._get_user(user_id)
        quota = self._effective_quota(user)
        if quota is not None:
            current = self._count_projects(user.id)
            if current >= quota:
                raise ProjectQuotaExceeded(user, quota)

        project = Project(user_id=user.id, name=name, status=status)
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def remaining_quota(self, user: User) -> Optional[int]:
        """Return how many additional projects the user can create."""

        quota = self._effective_quota(user)
        if quota is None:
            return None
        used = self._count_projects(user.id)
        remaining = quota - used
        return max(0, remaining)

    def quota_summary(self, user: User | int) -> dict[str, Optional[int]]:
        """Return quota information (limit/used/remaining) for a user."""

        if isinstance(user, User):
            user_obj = self._get_user(user.id)
        else:
            user_obj = self._get_user(int(user))

        quota = self._effective_quota(user_obj)
        used = self._count_projects(user_obj.id)
        remaining = self.remaining_quota(user_obj)

        return {
            "user_id": user_obj.id,
            "limit": quota,
            "used": used,
            "remaining": remaining,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_user(self, user_id: int) -> User:
        user = self.db.get(User, user_id)
        if user is None:
            raise UserNotFound(user_id)
        return user

    def _effective_quota(self, user: User) -> Optional[int]:
        if user.quota_projects is not None:
            return user.quota_projects

        assert self.settings is not None  # for type checkers
        default_quota = getattr(self.settings, "default_project_quota", 0)
        if default_quota <= 0:
            return None
        return default_quota

    def _count_projects(self, user_id: int) -> int:
        return int(
            self.db.query(func.count(Project.id))
            .filter(Project.user_id == user_id)
            .scalar()
            or 0
        )


__all__ = [
    "ProjectService",
    "ProjectServiceError",
    "ProjectQuotaExceeded",
    "UserNotFound",
]

