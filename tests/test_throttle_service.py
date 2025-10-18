from __future__ import annotations

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
    Task,
    TaskStatus,
    User,
)
from tgac.api.services.throttle import AdaptiveThrottle
from tgac.api.utils.time import utcnow


def setup_module(module) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


def teardown_module(module) -> None:
    Base.metadata.drop_all(module.engine)


def setup_function(function) -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def _prepare_context(session: Session) -> tuple[Project, Channel, Task, Account]:
    user = User(username="throttle-user")
    session.add(user)
    session.flush()

    project = Project(user_id=user.id, name="Throttle Project")
    session.add(project)
    session.flush()

    channel = Channel(project_id=project.id, title="Throttle Channel")
    session.add(channel)
    session.flush()

    task = Task(project_id=project.id, name="Primary task", status=TaskStatus.ON)
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

    session.commit()

    return project, channel, task, account


def test_project_factor_returns_full_without_checks() -> None:
    session = TestingSession()
    try:
        project, _, _, _ = _prepare_context(session)
        throttle = AdaptiveThrottle(session)

        assert throttle.project_factor(project.id) == 1.0
    finally:
        session.close()


def test_project_factor_reacts_to_visibility_drop() -> None:
    session = TestingSession()
    try:
        project, channel, task, account = _prepare_context(session)

        for idx in range(20):
            session.add(
                Comment(
                    account_id=account.id,
                    task_id=task.id,
                    channel_id=channel.id,
                    post_id=idx + 10,
                    result=CommentResult.SUCCESS,
                    visible=idx < 8,
                    visibility_checked_at=utcnow(),
                )
            )
        session.commit()

        throttle = AdaptiveThrottle(session)

        factor = throttle.project_factor(project.id)
        assert factor == 0.45

        allowed_many = throttle.allowed_for(project.id, 10)
        assert allowed_many == 4

        allowed_single = throttle.allowed_for(project.id, 1)
        assert allowed_single == 1
    finally:
        session.close()
