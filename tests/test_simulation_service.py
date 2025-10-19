import os
from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models.base import Base
from tgac.api.models.core import (
    Account,
    AccountChannelMap,
    AccountStatus,
    Channel,
    Post,
    Project,
    Task,
    TaskAssignment,
    TaskMode,
    TaskStatus,
    User,
)
from tgac.api.services.comment_engine import CommentEngine
from tgac.api.services.simulation import (
    InvalidLimit,
    SimulationService,
    TaskNotFound,
)
from tgac.api.utils.time import utcnow

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("BASE_URL", "https://example.com")
os.environ.setdefault("DB_URL", "sqlite:///./tests.db")
os.environ.setdefault("SESSION_SECRET_KEY", "secret")


def setup_module(module):
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


def teardown_module(module):
    Base.metadata.drop_all(module.engine)
    module.engine.dispose()


def setup_function(function):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def _prepare_task(session: Session) -> tuple[Task, list[Post]]:
    user = User(username="simulation-user")
    session.add(user)
    session.flush()

    project = Project(user_id=user.id, name="Simulation Project")
    session.add(project)
    session.flush()

    channel = Channel(project_id=project.id, title="Simulation Channel")
    session.add(channel)
    session.flush()

    posts: list[Post] = []
    for idx in range(3):
        post = Post(
            channel_id=channel.id,
            post_id=100 + idx,
            detected_at=utcnow() - timedelta(minutes=idx),
        )
        session.add(post)
        session.flush()
        posts.append(post)

    task = Task(
        project_id=project.id,
        name="Dry Run",
        status=TaskStatus.ON,
        mode=TaskMode.NEW_POSTS,
    )
    session.add(task)
    session.flush()

    account = Account(
        project_id=project.id,
        phone="+79991234567",
        session_enc=b"enc",
        status=AccountStatus.ACTIVE,
    )
    session.add(account)
    session.flush()

    session.add(TaskAssignment(task_id=task.id, account_id=account.id))
    session.add(
        AccountChannelMap(
            account_id=account.id,
            channel_id=channel.id,
            is_subscribed=True,
        )
    )
    session.commit()

    return task, posts


def test_task_dry_run_returns_previews():
    session = TestingSession()
    try:
        task, posts = _prepare_task(session)
        service = SimulationService(
            session,
            engine_factory=lambda db: CommentEngine(db),
        )

        previews = service.task_dry_run(task.id, limit=2)

        assert len(previews) == 2
        returned_ids = [item.preview.post_id for item in previews]
        expected_ids = [posts[0].id, posts[1].id]
        assert returned_ids == expected_ids
        assert all(item.preview.ready for item in previews)
    finally:
        session.close()


def test_task_dry_run_handles_invalid_inputs():
    session = TestingSession()
    try:
        service = SimulationService(session)
        with pytest.raises(InvalidLimit):
            service.task_dry_run(1, limit=0)

        with pytest.raises(TaskNotFound):
            service.task_dry_run(999)
    finally:
        session.close()
