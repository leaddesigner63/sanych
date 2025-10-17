from __future__ import annotations

from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models.base import Base
from tgac.api.models.core import Account, Channel, Comment, CommentResult, Project, Task, User
from tgac.api.services.observer import ObserverService
from tgac.api.utils.time import utcnow


def setup_module(module):
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


def setup_function(function):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def _prepare_entities(session: Session) -> tuple[Channel, Task, Account]:
    user = User(username="observer-user")
    session.add(user)
    session.flush()

    project = Project(user_id=user.id, name="Observer Project")
    session.add(project)
    session.flush()

    channel = Channel(project_id=project.id, title="Observer Channel")
    session.add(channel)
    session.flush()

    task = Task(project_id=project.id, name="Observer Task")
    session.add(task)
    session.flush()

    account = Account(project_id=project.id, phone="+79990000000", session_enc=b"0")
    session.add(account)
    session.flush()

    return channel, task, account


def _create_comment(
    session: Session,
    *,
    post_suffix: int,
    sent_delta: timedelta = timedelta(minutes=10),
    visibility_delta: timedelta | None = None,
) -> Comment:
    channel, task, account = _prepare_entities(session)
    comment = Comment(
        account_id=account.id,
        channel_id=channel.id,
        task_id=task.id,
        post_id=10_000 + post_suffix,
        result=CommentResult.SUCCESS,
        sent_at=utcnow() - sent_delta,
    )
    if visibility_delta is not None:
        comment.visibility_checked_at = utcnow() - visibility_delta
        comment.visible = True
    session.add(comment)
    session.commit()
    session.refresh(comment)
    return comment


def test_run_once_updates_visibility_flags():
    session = TestingSession()
    try:
        comment = _create_comment(session, post_suffix=1)
        calls: list[int] = []

        def probe(record: Comment) -> bool:
            calls.append(record.id)
            return False

        service = ObserverService(
            session,
            probe=probe,
            stale_after=timedelta(minutes=5),
            batch_size=10,
        )

        processed = service.run_once()

        assert processed == 1
        assert calls == [comment.id]
        session.refresh(comment)
        assert comment.visible is False
        assert comment.visibility_checked_at is not None
    finally:
        session.close()


def test_pending_comments_skip_recently_checked():
    session = TestingSession()
    try:
        _create_comment(session, post_suffix=2, visibility_delta=timedelta(minutes=1))

        service = ObserverService(
            session,
            probe=lambda record: True,
            stale_after=timedelta(minutes=5),
            batch_size=10,
        )

        assert service.pending_comments() == []
    finally:
        session.close()
