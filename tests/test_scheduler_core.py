from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models.base import Base
from tgac.api.models.core import (
    Account,
    Channel,
    Comment,
    CommentResult,
    Job,
    Post,
    Project,
    User,
    Task,
)
from tgac.api.services.scheduler_core import SchedulerCore


def setup_module(module):
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


def setup_function(function):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def _make_post(session: Session, suffix: str) -> tuple[Post, Channel, Project]:
    user = User(username=f"user-{suffix}")
    session.add(user)
    session.flush()

    project = Project(user_id=user.id, name=f"Project {suffix}")
    session.add(project)
    session.flush()

    channel = Channel(project_id=project.id, title=f"Channel {suffix}")
    session.add(channel)
    session.flush()

    post = Post(channel_id=channel.id, post_id=1000 + len(suffix))
    session.add(post)
    session.flush()

    return post, channel, project


def test_plan_for_posts_skips_when_pending_job_exists():
    session = TestingSession()
    try:
        post, _, _ = _make_post(session, "pending")
        core = SchedulerCore(session, comment_collision_limit=1)

        first = core.plan_for_posts([post])
        assert first == 1
        assert session.query(Job).count() == 1

        second = core.plan_for_posts([post])
        assert second == 0
        assert session.query(Job).count() == 1
    finally:
        session.close()


def test_plan_for_posts_skips_when_success_comment_exists():
    session = TestingSession()
    try:
        post, channel, project = _make_post(session, "commented")
        account = Account(project_id=project.id, phone="+79000000001", session_enc=b"0")
        session.add(account)
        session.flush()

        task = Task(project_id=project.id, name="Task for comments")
        session.add(task)
        session.flush()

        comment = Comment(
            account_id=account.id,
            task_id=task.id,
            channel_id=channel.id,
            post_id=post.post_id,
            result=CommentResult.SUCCESS,
        )
        session.add(comment)
        session.commit()

        core = SchedulerCore(session, comment_collision_limit=1)
        planned = core.plan_for_posts([post])

        assert planned == 0
        assert session.query(Job).count() == 0
    finally:
        session.close()

