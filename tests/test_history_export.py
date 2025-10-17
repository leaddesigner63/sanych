from __future__ import annotations

import json
from datetime import datetime, timedelta
from io import BytesIO
import csv
from zipfile import ZipFile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from uuid import uuid4

from tgac.api.models.base import Base
from tgac.api.models.core import (
    Account,
    AccountStatus,
    Channel,
    Comment,
    CommentResult,
    Playlist,
    PlaylistChannel,
    Project,
    ProjectStatus,
    Proxy,
    ProxyScheme,
    Task,
    TaskAssignment,
    TaskMode,
    TaskStatus,
    User,
)
from tgac.api.services.export import ExportService, ProjectNotFound
from tgac.api.services.history import AccountNotFound, HistoryService, TaskNotFound
from tgac.api.utils.time import utcnow


def setup_module(module):
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


def create_project_with_entities(session: Session, *, suffix: str | None = None) -> tuple[Project, Account, Task, Comment]:
    suffix = suffix or uuid4().hex
    numeric_suffix = ("".join(ch for ch in suffix if ch.isdigit()) or "0")[:3].ljust(3, "0")

    user = User(username=f"history-export-owner-{suffix}")
    session.add(user)
    session.flush()

    project = Project(user_id=user.id, name=f"History Export {suffix}", status=ProjectStatus.ACTIVE)
    session.add(project)
    session.flush()

    proxy = Proxy(
        project_id=project.id,
        name=f"proxy-main-{suffix}",
        scheme=ProxyScheme.HTTP,
        host="127.0.0.1",
        port=9000,
        username="user",
        password="pass",
    )
    session.add(proxy)
    session.flush()

    account = Account(
        project_id=project.id,
        phone=f"+100000000{numeric_suffix}",
        session_enc=b"enc",
        status=AccountStatus.ACTIVE,
        proxy_id=proxy.id,
        tags="vip",
        notes="checked",
        last_health_at=utcnow() - timedelta(hours=1),
        last_comment_at=utcnow() - timedelta(minutes=30),
    )
    session.add(account)
    session.flush()

    channel = Channel(
        project_id=project.id,
        title="Channel",
        username="channel",
        tg_id=123,
        link="https://t.me/channel",
    )
    session.add(channel)
    session.flush()

    playlist = Playlist(project_id=project.id, name=f"Playlist {suffix}", desc="desc")
    session.add(playlist)
    session.flush()

    mapping = PlaylistChannel(playlist_id=playlist.id, channel_id=channel.id)
    session.add(mapping)

    task = Task(project_id=project.id, name=f"Task {suffix}", status=TaskStatus.ON, mode=TaskMode.NEW_POSTS)
    session.add(task)
    session.flush()

    assignment = TaskAssignment(task_id=task.id, account_id=account.id)
    session.add(assignment)

    comment = Comment(
        account_id=account.id,
        task_id=task.id,
        channel_id=channel.id,
        post_id=42,
        result=CommentResult.SUCCESS,
        sent_at=utcnow(),
        planned_at=utcnow() - timedelta(minutes=5),
        template="Hi",
        rendered="Hi there",
    )
    session.add(comment)
    session.commit()

    return project, account, task, comment


def test_history_service_orders_by_sent_at_descending():
    session = TestingSession()
    try:
        project, account, task, comment = create_project_with_entities(session)

        older_comment = Comment(
            account_id=account.id,
            task_id=task.id,
            channel_id=comment.channel_id,
            post_id=24,
            result=CommentResult.ERROR,
            sent_at=comment.sent_at - timedelta(hours=2),
        )
        session.add(older_comment)
        session.commit()

        service = HistoryService(session)

        account_history = service.account_history(account.id)
        assert [item.post_id for item in account_history] == [comment.post_id, older_comment.post_id]

        task_history = service.task_history(task.id)
        assert [item.id for item in task_history] == [comment.id, older_comment.id]
    finally:
        session.close()


def test_history_service_validates_entities():
    session = TestingSession()
    try:
        service = HistoryService(session)
        with pytest.raises(AccountNotFound):
            service.account_history(999)
        with pytest.raises(TaskNotFound):
            service.task_history(999)
    finally:
        session.close()


def test_export_service_creates_zip_archive():
    session = TestingSession()
    try:
        project, account, task, comment = create_project_with_entities(session)

        service = ExportService(session)
        payload = service.build_project_archive(project.id)

        archive = ZipFile(BytesIO(payload))
        names = set(archive.namelist())
        assert {
            "metadata.json",
            "project.json",
            "accounts.json",
            "proxies.json",
            "channels.json",
            "playlists.json",
            "tasks.json",
            "comments.json",
            "metrics.csv",
        }.issubset(names)

        project_data = json.loads(archive.read("project.json"))
        assert project_data["name"] == project.name

        accounts_data = json.loads(archive.read("accounts.json"))
        assert accounts_data[0]["phone"] == account.phone

        tasks_data = json.loads(archive.read("tasks.json"))
        assert tasks_data[0]["assignments"] == [account.id]

        comments_data = json.loads(archive.read("comments.json"))
        assert {entry["post_id"] for entry in comments_data} == {comment.post_id}

        metrics_reader = csv.DictReader(archive.read("metrics.csv").decode("utf-8").splitlines())
        metrics_rows = {row["key"]: row["value"] for row in metrics_reader}
        assert metrics_rows["comments_total"] == "1"
        assert metrics_rows["accounts_total"] == "1"
    finally:
        session.close()


def test_export_service_requires_existing_project():
    session = TestingSession()
    try:
        service = ExportService(session)
        with pytest.raises(ProjectNotFound):
            service.build_project_archive(404)
    finally:
        session.close()
