import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models.base import Base
from tgac.api.models.core import (
    Account,
    AccountChannelMap,
    AccountStatus,
    Channel,
    Comment,
    CommentResult,
    Job,
    JobStatus,
    JobType,
    Post,
    Project,
    Task,
    TaskAssignment,
    TaskMode,
    TaskStatus,
    User,
)
from tgac.api.services.comment_engine import CommentEngine, SendResult
from tgac.api.services.scheduler_core import SchedulerCore
from tgac.workers.worker import process_job

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


def setup_function(function):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def _make_project(session: Session) -> tuple[Project, Channel, Post, Task, Account]:
    user = User(username="comment-engine-user")
    session.add(user)
    session.flush()

    project = Project(user_id=user.id, name="Comment Project")
    session.add(project)
    session.flush()

    channel = Channel(project_id=project.id, title="Comment Channel")
    session.add(channel)
    session.flush()

    post = Post(channel_id=channel.id, post_id=101)
    session.add(post)
    session.flush()

    task = Task(
        project_id=project.id,
        name="Primary task",
        status=TaskStatus.ON,
        mode=TaskMode.NEW_POSTS,
        config={"template": "Hello"},
    )
    session.add(task)
    session.flush()

    account = Account(
        project_id=project.id,
        phone="+79990000001",
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

    session.refresh(post)
    session.refresh(task)
    session.refresh(account)

    return project, channel, post, task, account


def test_plan_for_post_filters_accounts_and_deduplicates():
    session = TestingSession()
    try:
        project, channel, post, task, account = _make_project(session)

        paused_account = Account(
            project_id=project.id,
            phone="+79990000002",
            session_enc=b"enc",
            status=AccountStatus.ACTIVE,
            is_paused=True,
        )
        session.add(paused_account)
        session.flush()
        session.add(TaskAssignment(task_id=task.id, account_id=paused_account.id))
        session.add(
            AccountChannelMap(
                account_id=paused_account.id,
                channel_id=channel.id,
                is_subscribed=True,
            )
        )

        foreign_account = Account(
            project_id=project.id,
            phone="+79990000003",
            session_enc=b"enc",
            status=AccountStatus.BANNED,
        )
        session.add(foreign_account)
        session.flush()
        session.add(TaskAssignment(task_id=task.id, account_id=foreign_account.id))
        session.commit()

        engine = CommentEngine(session)

        created = engine.plan_for_post(post.id)
        assert len(created) == 1
        assert created[0].account_id == account.id
        assert created[0].template == task.config["template"]
        assert created[0].rendered == "Hello"

        # A second run should be a no-op because comments already exist.
        created_again = engine.plan_for_post(post.id)
        assert created_again == []

        jobs = session.query(Job).filter(Job.type == JobType.SEND_COMMENT).all()
        assert len(jobs) == 1
        assert jobs[0].status == JobStatus.PENDING
    finally:
        session.close()


def test_send_comment_records_outcome():
    session = TestingSession()
    try:
        _, _, post, _, _ = _make_project(session)
        engine = CommentEngine(session)
        comments = engine.plan_for_post(post.id)
        comment = comments[0]

        failing_engine = CommentEngine(
            session,
            sender=lambda _: SendResult(
                result=CommentResult.ERROR,
                error_code="FLOOD",
                error_message="Rate limit",
                rendered="Rendered",
            ),
        )

        outcome = failing_engine.send_comment(comment.id)
        assert not outcome.success

        session.refresh(comment)
        assert comment.result == CommentResult.ERROR
        assert comment.error_code == "FLOOD"
        assert comment.error_msg == "Rate limit"
        assert comment.rendered == "Rendered"
        assert comment.sent_at is not None
    finally:
        session.close()


def test_worker_processes_plan_and_send_jobs():
    session = TestingSession()
    try:
        _, _, post, _, _ = _make_project(session)
        job = Job(type=JobType.PLAN_COMMENTS, payload={"post_id": post.id})
        session.add(job)
        session.commit()

        core = SchedulerCore(session)
        picked = core.pick_next_job("worker-test")
        assert picked is not None

        process_job(core, picked, engine=CommentEngine(session))

        session.expire_all()
        planned_job = session.get(Job, job.id)
        assert planned_job.status == JobStatus.DONE

        next_job = core.pick_next_job("worker-test")
        assert next_job is not None
        assert next_job.type == JobType.SEND_COMMENT

        process_job(
            core,
            next_job,
            engine=CommentEngine(
                session,
                sender=lambda comment: SendResult(result=CommentResult.SUCCESS),
            ),
        )

        session.expire_all()
        comment_job = session.get(Job, next_job.id)
        assert comment_job.status == JobStatus.DONE

        send_jobs = session.query(Job).filter(Job.type == JobType.SEND_COMMENT).all()
        assert len(send_jobs) == 1
        assert send_jobs[0].status == JobStatus.DONE

        comment_id = send_jobs[0].payload.get("comment_id")
        assert comment_id is not None

        final_comment = session.get(Comment, comment_id)
        assert final_comment is not None
        assert final_comment.result == CommentResult.SUCCESS
        assert final_comment.sent_at is not None
    finally:
        session.close()


def test_subscription_job_marks_mapping_and_triggers_comment_plan():
    session = TestingSession()
    try:
        _, channel, post, _, account = _make_project(session)
        mapping = (
            session.query(AccountChannelMap)
            .filter(
                AccountChannelMap.account_id == account.id,
                AccountChannelMap.channel_id == channel.id,
            )
            .one()
        )
        mapping.is_subscribed = False
        mapping.last_subscribed_at = None
        session.commit()

        engine = CommentEngine(session)
        created = engine.plan_for_post(post.id)
        assert created == []

        subscribe_job = (
            session.query(Job)
            .filter(Job.type == JobType.SUBSCRIBE)
            .one()
        )
        assert subscribe_job.payload["account_id"] == account.id
        assert subscribe_job.payload["channel_id"] == channel.id

        core = SchedulerCore(session)
        picked = core.pick_next_job("worker-subscribe")
        assert picked is not None
        assert picked.type == JobType.SUBSCRIBE

        process_job(core, picked, engine=CommentEngine(session))

        session.expire_all()
        updated_mapping = (
            session.query(AccountChannelMap)
            .filter(
                AccountChannelMap.account_id == account.id,
                AccountChannelMap.channel_id == channel.id,
            )
            .one()
        )
        assert updated_mapping.is_subscribed is True
        assert updated_mapping.last_subscribed_at is not None

        next_job = core.pick_next_job("worker-send")
        assert next_job is not None
        assert next_job.type == JobType.SEND_COMMENT

        process_job(
            core,
            next_job,
            engine=CommentEngine(
                session,
                sender=lambda _: SendResult(result=CommentResult.SUCCESS),
            ),
        )

        session.expire_all()
        comment = session.query(Comment).one()
        assert comment.result == CommentResult.SUCCESS
    finally:
        session.close()
