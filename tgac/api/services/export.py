from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO, StringIO
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.core import (
    Account,
    Comment,
    Channel,
    Playlist,
    PlaylistChannel,
    Project,
    Proxy,
    Task,
    TaskAssignment,
)
from ..utils.time import utcnow
from .metrics import MetricsService, ProjectMetric


def _serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class ExportServiceError(Exception):
    """Base error for export failures."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class ProjectNotFound(ExportServiceError):
    """Raised when the target project does not exist."""


@dataclass
class ExportService:
    """Aggregate project data into a downloadable archive."""

    db: Session

    def build_project_archive(self, project_id: int) -> bytes:
        project = self.db.get(Project, project_id)
        if project is None:
            raise ProjectNotFound(f"Project {project_id} not found", status_code=404)

        payload = self._collect_payload(project)
        buffer = BytesIO()
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
            for name, data in payload.items():
                if isinstance(data, bytes):
                    archive.writestr(name, data)
                elif isinstance(data, str):
                    archive.writestr(name, data.encode("utf-8"))
                else:
                    archive.writestr(name, json.dumps(data, ensure_ascii=False, indent=2))
        buffer.seek(0)
        return buffer.read()

    def _collect_payload(self, project: Project) -> dict[str, Any]:
        project_id = project.id

        accounts = (
            self.db.query(Account)
            .filter(Account.project_id == project_id)
            .order_by(Account.id.asc())
            .all()
        )
        proxies = (
            self.db.query(Proxy)
            .filter(Proxy.project_id == project_id)
            .order_by(Proxy.id.asc())
            .all()
        )
        channels = (
            self.db.query(Channel)
            .filter(Channel.project_id == project_id)
            .order_by(Channel.id.asc())
            .all()
        )
        playlists = (
            self.db.query(Playlist)
            .filter(Playlist.project_id == project_id)
            .order_by(Playlist.id.asc())
            .all()
        )
        playlist_channels = (
            self.db.query(PlaylistChannel)
            .join(Playlist, PlaylistChannel.playlist_id == Playlist.id)
            .filter(Playlist.project_id == project_id)
            .order_by(PlaylistChannel.id.asc())
            .all()
        )
        tasks = (
            self.db.query(Task)
            .filter(Task.project_id == project_id)
            .order_by(Task.id.asc())
            .all()
        )
        assignments = (
            self.db.query(TaskAssignment)
            .join(Task, TaskAssignment.task_id == Task.id)
            .filter(Task.project_id == project_id)
            .order_by(TaskAssignment.id.asc())
            .all()
        )

        account_ids = [account.id for account in accounts]
        channel_ids = [channel.id for channel in channels]
        task_ids = [task.id for task in tasks]

        comment_conditions = []
        if account_ids:
            comment_conditions.append(Comment.account_id.in_(account_ids))
        if channel_ids:
            comment_conditions.append(Comment.channel_id.in_(channel_ids))
        if task_ids:
            comment_conditions.append(Comment.task_id.in_(task_ids))

        if comment_conditions:
            comments = (
                self.db.query(Comment)
                .filter(or_(*comment_conditions))
                .order_by(Comment.id.asc())
                .all()
            )
        else:
            comments = []

        playlist_map: dict[int, list[int]] = {}
        for mapping in playlist_channels:
            playlist_map.setdefault(mapping.playlist_id, []).append(mapping.channel_id)

        assignment_map: dict[int, list[int]] = {}
        for mapping in assignments:
            assignment_map.setdefault(mapping.task_id, []).append(mapping.account_id)

        payload: dict[str, Any] = {}

        payload["metadata.json"] = {
            "project_id": project_id,
            "generated_at": utcnow().isoformat(),
            "entity_counts": {
                "accounts": len(accounts),
                "proxies": len(proxies),
                "channels": len(channels),
                "playlists": len(playlists),
                "tasks": len(tasks),
            },
        }

        payload["project.json"] = {
            "id": project.id,
            "user_id": project.user_id,
            "name": project.name,
            "status": project.status.value,
            "created_at": _serialize_datetime(project.created_at),
        }

        payload["accounts.json"] = [
            {
                "id": account.id,
                "phone": account.phone,
                "status": account.status.value,
                "proxy_id": account.proxy_id,
                "is_paused": account.is_paused,
                "tags": account.tags,
                "notes": account.notes,
                "last_health_at": _serialize_datetime(account.last_health_at),
                "last_comment_at": _serialize_datetime(account.last_comment_at),
            }
            for account in accounts
        ]

        payload["proxies.json"] = [
            {
                "id": proxy.id,
                "name": proxy.name,
                "scheme": proxy.scheme.value,
                "host": proxy.host,
                "port": proxy.port,
                "username": proxy.username,
                "password": proxy.password,
                "is_working": proxy.is_working,
                "last_check_at": _serialize_datetime(proxy.last_check_at),
            }
            for proxy in proxies
        ]

        payload["channels.json"] = [
            {
                "id": channel.id,
                "title": channel.title,
                "username": channel.username,
                "tg_id": channel.tg_id,
                "link": channel.link,
                "active": channel.active,
                "created_at": _serialize_datetime(channel.created_at),
                "last_scanned_at": _serialize_datetime(channel.last_scanned_at),
            }
            for channel in channels
        ]

        payload["playlists.json"] = [
            {
                "id": playlist.id,
                "name": playlist.name,
                "desc": playlist.desc,
                "channel_ids": playlist_map.get(playlist.id, []),
                "created_at": _serialize_datetime(playlist.created_at),
                "updated_at": _serialize_datetime(playlist.updated_at),
            }
            for playlist in playlists
        ]

        payload["tasks.json"] = [
            {
                "id": task.id,
                "name": task.name,
                "status": task.status.value,
                "mode": task.mode.value,
                "config": task.config,
                "assignments": assignment_map.get(task.id, []),
                "created_at": _serialize_datetime(task.created_at),
                "updated_at": _serialize_datetime(task.updated_at),
            }
            for task in tasks
        ]

        payload["comments.json"] = [
            {
                "id": comment.id,
                "account_id": comment.account_id,
                "task_id": comment.task_id,
                "channel_id": comment.channel_id,
                "post_id": comment.post_id,
                "message_id": comment.message_id,
                "thread_id": comment.thread_id,
                "result": comment.result.value if comment.result else None,
                "planned_at": _serialize_datetime(comment.planned_at),
                "sent_at": _serialize_datetime(comment.sent_at),
                "template": comment.template,
                "rendered": comment.rendered,
                "error_code": comment.error_code,
                "error_msg": comment.error_msg,
                "visible": comment.visible,
                "visibility_checked_at": _serialize_datetime(comment.visibility_checked_at),
            }
            for comment in comments
        ]

        metrics_service = MetricsService(self.db)
        metrics = metrics_service.collect_project_metrics(project_id)
        payload["metrics.csv"] = self._metrics_to_csv(metrics)

        return payload

    @staticmethod
    def _metrics_to_csv(metrics: list[ProjectMetric]) -> str:
        buffer = StringIO()
        writer = csv.DictWriter(buffer, fieldnames=["key", "value", "description"])
        writer.writeheader()
        for metric in metrics:
            row = metric.as_dict()
            value = row["value"]
            writer.writerow(
                {
                    "key": row["key"],
                    "value": "" if value is None else value,
                    "description": row["description"],
                }
            )
        return buffer.getvalue()


__all__ = [
    "ExportService",
    "ExportServiceError",
    "ProjectNotFound",
]
