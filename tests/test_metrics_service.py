from __future__ import annotations

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models.base import Base
from tgac.api.models.core import (
    Account,
    AccountStatus,
    Channel,
    Comment,
    CommentResult,
    Project,
    ProjectStatus,
    Proxy,
    ProxyScheme,
    Task,
    TaskStatus,
    User,
)
from tgac.api.services.metrics import MetricsService, ProjectNotFound


def setup_module(module) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


def setup_function(function) -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def _create_project_with_entities(session: Session) -> Project:
    user = User(username="metrics-user")
    session.add(user)
    session.flush()

    project = Project(user_id=user.id, name="Metrics Project", status=ProjectStatus.ACTIVE)
    session.add(project)
    session.flush()

    proxy_ok = Proxy(
        project_id=project.id,
        name="proxy-ok",
        scheme=ProxyScheme.HTTP,
        host="127.0.0.1",
        port=8000,
        is_working=True,
    )
    proxy_bad = Proxy(
        project_id=project.id,
        name="proxy-bad",
        scheme=ProxyScheme.HTTP,
        host="127.0.0.1",
        port=8001,
        is_working=False,
    )
    session.add_all([proxy_ok, proxy_bad])
    session.flush()

    account_active = Account(
        project_id=project.id,
        phone="+10000000001",
        session_enc=b"1",
        status=AccountStatus.ACTIVE,
        proxy_id=proxy_ok.id,
    )
    account_paused = Account(
        project_id=project.id,
        phone="+10000000002",
        session_enc=b"2",
        status=AccountStatus.ACTIVE,
        is_paused=True,
    )
    account_banned = Account(
        project_id=project.id,
        phone="+10000000003",
        session_enc=b"3",
        status=AccountStatus.BANNED,
    )
    session.add_all([account_active, account_paused, account_banned])
    session.flush()

    channel = Channel(project_id=project.id, title="Metrics Channel")
    session.add(channel)
    session.flush()

    task_on = Task(project_id=project.id, name="Task ON", status=TaskStatus.ON)
    task_off = Task(project_id=project.id, name="Task OFF", status=TaskStatus.OFF)
    session.add_all([task_on, task_off])
    session.flush()

    success_comment = Comment(
        account_id=account_active.id,
        task_id=task_on.id,
        channel_id=channel.id,
        post_id=10,
        result=CommentResult.SUCCESS,
        visible=True,
        visibility_checked_at=datetime.utcnow(),
    )
    error_comment = Comment(
        account_id=account_active.id,
        task_id=task_on.id,
        channel_id=channel.id,
        post_id=11,
        result=CommentResult.ERROR,
        visible=False,
        visibility_checked_at=datetime.utcnow(),
    )
    skipped_comment = Comment(
        account_id=account_paused.id,
        task_id=task_on.id,
        channel_id=channel.id,
        post_id=12,
        result=CommentResult.SKIPPED,
    )
    session.add_all([success_comment, error_comment, skipped_comment])
    session.commit()

    return project


def test_collect_project_metrics_aggregates_values() -> None:
    session = TestingSession()
    try:
        project = _create_project_with_entities(session)
        service = MetricsService(session)
        metrics = service.collect_project_metrics(project.id)
        values = {metric.key: metric.value for metric in metrics}

        assert values["accounts_total"] == 3
        assert values["accounts_active"] == 1
        assert values["accounts_paused"] == 1
        assert values["accounts_banned"] == 1
        assert values["proxies_total"] == 2
        assert values["proxies_working"] == 1
        assert values["channels_total"] == 1
        assert values["tasks_total"] == 2
        assert values["tasks_active"] == 1
        assert values["comments_total"] == 3
        assert values["comments_success"] == 1
        assert values["comments_error"] == 1
        assert values["comments_skipped"] == 1
        assert values["comment_success_rate"] == 0.3333
        assert values["comments_visibility_checked"] == 2
        assert values["comments_visible"] == 1
        assert values["comment_visibility_rate"] == 0.5
    finally:
        session.close()


def test_collect_project_metrics_requires_existing_project() -> None:
    session = TestingSession()
    try:
        service = MetricsService(session)
        with pytest.raises(ProjectNotFound):
            service.collect_project_metrics(12345)
    finally:
        session.close()
