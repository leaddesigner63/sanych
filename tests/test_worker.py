from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models.base import Base
from tgac.api.models.core import Account, JobStatus, JobType, Project, User
from tgac.api.services.scheduler_core import SchedulerCore
from tgac.workers.worker import process_job


def setup_module(module):
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


def setup_function(function):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def _create_account(session: Session) -> Account:
    user = User(username="worker-user")
    session.add(user)
    session.flush()

    project = Project(user_id=user.id, name="Worker Project")
    session.add(project)
    session.flush()

    account = Account(project_id=project.id, phone="+79990000000", session_enc=b"0")
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def test_process_healthcheck_job_updates_account_timestamp():
    session = TestingSession()
    try:
        account = _create_account(session)
        core = SchedulerCore(session, comment_collision_limit=1)

        job = core.enqueue(JobType.HEALTHCHECK, {"account_id": account.id})
        assert job.status == JobStatus.PENDING

        process_job(core, job)

        session.refresh(account)
        session.refresh(job)
        assert job.status == JobStatus.DONE
        assert account.last_health_at is not None
    finally:
        session.close()
