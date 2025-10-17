from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ..models.core import (
    Account,
    AccountStatus,
    Channel,
    Comment,
    CommentResult,
    Project,
    Proxy,
    Task,
    TaskStatus,
)


class MetricsServiceError(Exception):
    """Base class for metrics related exceptions."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class ProjectNotFound(MetricsServiceError):
    """Raised when metrics are requested for a missing project."""


@dataclass(frozen=True, slots=True)
class ProjectMetric:
    """Single metric entry returned to API consumers and exporters."""

    key: str
    value: float | int | None
    description: str

    def as_dict(self) -> dict[str, float | int | None | str]:
        return {
            "key": self.key,
            "value": self.value,
            "description": self.description,
        }


@dataclass(slots=True)
class MetricsService:
    """Aggregate operational metrics for dashboards and exports."""

    db: Session

    def collect_project_metrics(self, project_id: int) -> list[ProjectMetric]:
        project = self.db.get(Project, project_id)
        if project is None:
            raise ProjectNotFound(f"Project {project_id} not found", status_code=404)

        account_ids = self._ids(select(Account.id).filter(Account.project_id == project_id))
        channel_ids = self._ids(select(Channel.id).filter(Channel.project_id == project_id))
        task_ids = self._ids(select(Task.id).filter(Task.project_id == project_id))

        comment_filters: list = []
        if account_ids:
            comment_filters.append(Comment.account_id.in_(account_ids))
        if channel_ids:
            comment_filters.append(Comment.channel_id.in_(channel_ids))
        if task_ids:
            comment_filters.append(Comment.task_id.in_(task_ids))

        comments_query = None
        if comment_filters:
            comments_query = self.db.query(Comment).filter(or_(*comment_filters))

        metrics: list[ProjectMetric] = []

        accounts_total = self._count(Account.id, Account.project_id == project_id)
        accounts_active = self._count(
            Account.id,
            and_(Account.project_id == project_id, Account.status == AccountStatus.ACTIVE, Account.is_paused.is_(False)),
        )
        accounts_paused = self._count(
            Account.id,
            and_(Account.project_id == project_id, Account.is_paused.is_(True)),
        )
        accounts_banned = self._count(
            Account.id,
            and_(Account.project_id == project_id, Account.status == AccountStatus.BANNED),
        )

        proxies_total = self._count(Proxy.id, Proxy.project_id == project_id)
        proxies_working = self._count(
            Proxy.id, and_(Proxy.project_id == project_id, Proxy.is_working.is_(True))
        )

        channels_total = self._count(Channel.id, Channel.project_id == project_id)

        tasks_total = self._count(Task.id, Task.project_id == project_id)
        tasks_active = self._count(
            Task.id,
            and_(Task.project_id == project_id, Task.status == TaskStatus.ON),
        )

        metrics.extend(
            [
                ProjectMetric("accounts_total", accounts_total, "Total number of accounts in project"),
                ProjectMetric(
                    "accounts_active",
                    accounts_active,
                    "Accounts with ACTIVE status and not paused",
                ),
                ProjectMetric(
                    "accounts_paused",
                    accounts_paused,
                    "Accounts currently paused",
                ),
                ProjectMetric(
                    "accounts_banned",
                    accounts_banned,
                    "Accounts marked as BANNED",
                ),
                ProjectMetric("proxies_total", proxies_total, "Registered proxies for the project"),
                ProjectMetric(
                    "proxies_working",
                    proxies_working,
                    "Proxies flagged as working",
                ),
                ProjectMetric("channels_total", channels_total, "Channels attached to the project"),
                ProjectMetric("tasks_total", tasks_total, "Configured automation tasks"),
                ProjectMetric("tasks_active", tasks_active, "Tasks currently enabled"),
            ]
        )

        if comments_query is None:
            metrics.extend(
                [
                    ProjectMetric("comments_total", 0, "Total comments linked to the project"),
                    ProjectMetric("comments_success", 0, "Comments delivered successfully"),
                    ProjectMetric("comments_error", 0, "Comments finished with errors"),
                    ProjectMetric("comments_skipped", 0, "Comments skipped during execution"),
                    ProjectMetric("comment_success_rate", None, "Share of successful comments"),
                    ProjectMetric(
                        "comments_visibility_checked",
                        0,
                        "Comments with visibility checks performed",
                    ),
                    ProjectMetric("comments_visible", 0, "Comments still visible"),
                    ProjectMetric(
                        "comment_visibility_rate",
                        None,
                        "Share of checked comments that remain visible",
                    ),
                ]
            )
        else:
            total_comments = self._count_from_query(comments_query)
            success_comments = self._count_from_query(
                comments_query.filter(Comment.result == CommentResult.SUCCESS)
            )
            error_comments = self._count_from_query(
                comments_query.filter(Comment.result == CommentResult.ERROR)
            )
            skipped_comments = self._count_from_query(
                comments_query.filter(Comment.result == CommentResult.SKIPPED)
            )
            checked_comments = self._count_from_query(
                comments_query.filter(Comment.visibility_checked_at.isnot(None))
            )
            visible_comments = self._count_from_query(
                comments_query.filter(Comment.visible.is_(True))
            )

            metrics.extend(
                [
                    ProjectMetric("comments_total", total_comments, "Total comments linked to the project"),
                    ProjectMetric("comments_success", success_comments, "Comments delivered successfully"),
                    ProjectMetric("comments_error", error_comments, "Comments finished with errors"),
                    ProjectMetric("comments_skipped", skipped_comments, "Comments skipped during execution"),
                    ProjectMetric(
                        "comment_success_rate",
                        self._ratio(success_comments, total_comments),
                        "Share of successful comments",
                    ),
                    ProjectMetric(
                        "comments_visibility_checked",
                        checked_comments,
                        "Comments with visibility checks performed",
                    ),
                    ProjectMetric("comments_visible", visible_comments, "Comments still visible"),
                    ProjectMetric(
                        "comment_visibility_rate",
                        self._ratio(visible_comments, checked_comments),
                        "Share of checked comments that remain visible",
                    ),
                ]
            )

        return metrics

    def _ids(self, stmt) -> list[int]:
        return [row[0] for row in self.db.execute(stmt).all()]

    def _count(self, column, *conditions) -> int:
        query = self.db.query(func.count(column))
        if conditions:
            query = query.filter(*conditions)
        return int(query.scalar() or 0)

    @staticmethod
    def _ratio(numerator: int, denominator: int) -> float | None:
        if denominator <= 0:
            return None
        return round(numerator / denominator, 4)

    @staticmethod
    def _count_from_query(query) -> int:
        return int(query.with_entities(func.count()).scalar() or 0)


__all__ = [
    "MetricsService",
    "MetricsServiceError",
    "ProjectMetric",
    "ProjectNotFound",
]
