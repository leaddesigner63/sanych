from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models.base import Base
from tgac.api.models.core import (
    Account,
    Channel,
    Comment,
    CommentResult,
    Project,
    Task,
    User,
)
from tgac.api.utils.time import utcnow
from tgac.workers import observer


class RecordingLogger:
    def __init__(self) -> None:
        self.records: list[tuple[int, bool, datetime]] = []

    def comment_planned(self, comment: Comment) -> None:  # pragma: no cover - protocol stub
        return

    def comment_sent(self, comment: Comment) -> None:  # pragma: no cover - protocol stub
        return

    def comment_visibility_checked(
        self, comment: Comment, *, visible: bool, checked_at: datetime
    ) -> None:
        self.records.append((comment.id, visible, checked_at))


def setup_module(module):
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


def setup_function(function):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def _create_comment(*, last_checked_minutes: int | None = None) -> int:
    with TestingSession() as session:
        user = User(username="observer-worker-user")
        session.add(user)
        session.flush()

        project = Project(user_id=user.id, name="Observer Worker Project")
        session.add(project)
        session.flush()

        channel = Channel(project_id=project.id, title="Observer Worker Channel")
        session.add(channel)
        session.flush()

        task = Task(project_id=project.id, name="Observer Worker Task")
        session.add(task)
        session.flush()

        account = Account(project_id=project.id, phone="+79990000000", session_enc=b"0")
        session.add(account)
        session.flush()

        comment = Comment(
            account_id=account.id,
            channel_id=channel.id,
            task_id=task.id,
            post_id=42,
            result=CommentResult.SUCCESS,
            sent_at=utcnow() - timedelta(minutes=10),
        )

        if last_checked_minutes is not None:
            comment.visibility_checked_at = utcnow() - timedelta(minutes=last_checked_minutes)
            comment.visible = True

        session.add(comment)
        session.commit()
        return comment.id


def test_process_once_updates_visibility_and_logs():
    comment_id = _create_comment()
    logger = RecordingLogger()

    processed = observer.process_once(
        probe=lambda _: False,
        stale_minutes=5,
        batch_size=10,
        event_logger=logger,
        session_factory=TestingSession,
    )

    assert processed == 1

    with TestingSession() as session:
        refreshed = session.get(Comment, comment_id)
        assert refreshed is not None
        assert refreshed.visible is False
        assert refreshed.visibility_checked_at is not None

    assert logger.records and logger.records[0][0] == comment_id
    assert logger.records[0][1] is False


def test_process_once_skips_recently_checked_comments():
    comment_id = _create_comment(last_checked_minutes=1)
    logger = RecordingLogger()

    processed = observer.process_once(
        probe=lambda _: True,
        stale_minutes=5,
        batch_size=10,
        event_logger=logger,
        session_factory=TestingSession,
    )

    assert processed == 0

    with TestingSession() as session:
        refreshed = session.get(Comment, comment_id)
        assert refreshed is not None
        assert refreshed.visible is True
        assert refreshed.visibility_checked_at is not None

    assert logger.records == []

