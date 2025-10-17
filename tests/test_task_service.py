import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models import core  # noqa: F401 - ensure models are registered
from tgac.api.models.base import Base
from tgac.api.models.core import (
    Account,
    AccountStatus,
    Project,
    Task,
    TaskMode,
    TaskStatus,
    User,
)
from tgac.api.services.tasks import (
    MAX_ASSIGNMENTS_PER_REQUEST,
    AccountNotFound,
    AssignmentSummary,
    ProjectMismatch,
    TaskNotFound,
    TaskService,
)


def setup_module(module):
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


def make_project(session: Session, suffix: str) -> Project:
    user = User(username=f"user-{suffix}")
    session.add(user)
    session.flush()

    project = Project(user_id=user.id, name=f"Project-{suffix}")
    session.add(project)
    session.flush()
    return project


def make_account(session: Session, project_id: int, phone: str) -> Account:
    account = Account(
        project_id=project_id,
        phone=phone,
        session_enc=b"0",
        status=AccountStatus.NEEDS_LOGIN,
    )
    session.add(account)
    session.flush()
    return account


def make_task(session: Session, project_id: int, name: str) -> Task:
    task = Task(project_id=project_id, name=name, mode=TaskMode.NEW_POSTS, status=TaskStatus.ON, config={})
    session.add(task)
    session.flush()
    return task


def test_assign_accounts_enforces_request_limit():
    session = TestingSession()
    try:
        project = make_project(session, "limit")
        task = make_task(session, project.id, "Task limit")
        accounts = [
            make_account(session, project.id, f"+60000000{i:03}")
            for i in range(MAX_ASSIGNMENTS_PER_REQUEST + 5)
        ]

        service = TaskService(session, max_assignments_per_request=MAX_ASSIGNMENTS_PER_REQUEST)

        summary = service.assign_accounts(task.id, [account.id for account in accounts])
        assert isinstance(summary, AssignmentSummary)
        assert summary.applied == MAX_ASSIGNMENTS_PER_REQUEST
        assert summary.skipped == len(accounts) - MAX_ASSIGNMENTS_PER_REQUEST

        stats = service.stats(task.id)
        assert stats["assignments"] == MAX_ASSIGNMENTS_PER_REQUEST
    finally:
        session.close()


def test_assign_accounts_idempotent_and_deduplicated():
    session = TestingSession()
    try:
        project = make_project(session, "idem")
        task = make_task(session, project.id, "Task idem")
        first_account = make_account(session, project.id, "+70000000001")
        second_account = make_account(session, project.id, "+70000000002")

        service = TaskService(session, max_assignments_per_request=5)

        summary_first = service.assign_accounts(task.id, [first_account.id, first_account.id])
        assert summary_first.applied == 1
        assert summary_first.skipped == 0

        summary_second = service.assign_accounts(task.id, [first_account.id, second_account.id])
        assert summary_second.applied == 1
        assert summary_second.already_linked == 1
        assert summary_second.skipped == 0
    finally:
        session.close()


def test_assign_accounts_requires_same_project():
    session = TestingSession()
    try:
        project = make_project(session, "primary")
        other_project = make_project(session, "other")
        task = make_task(session, project.id, "Main task")
        foreign_account = make_account(session, other_project.id, "+71000000001")

        service = TaskService(session)

        with pytest.raises(ProjectMismatch):
            service.assign_accounts(task.id, [foreign_account.id])
    finally:
        session.close()


def test_assign_accounts_missing_entities():
    session = TestingSession()
    try:
        project = make_project(session, "missing")
        task = make_task(session, project.id, "Missing task")
        service = TaskService(session)

        with pytest.raises(AccountNotFound):
            service.assign_accounts(task.id, [9999])

        with pytest.raises(TaskNotFound):
            service.assign_accounts(9999, [])
    finally:
        session.close()
