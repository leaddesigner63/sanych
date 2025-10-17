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
    TaskAssignment,
    TaskMode,
    TaskStatus,
    User,
)
from tgac.api.services.tasks import (
    MAX_ASSIGNMENTS_PER_REQUEST,
    AccountNotFound,
    AssignmentSummary,
    InvalidFilter,
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


def make_account(
    session: Session,
    project_id: int,
    phone: str,
    *,
    status: AccountStatus = AccountStatus.NEEDS_LOGIN,
    tags: str | None = None,
    is_paused: bool = False,
) -> Account:
    account = Account(
        project_id=project_id,
        phone=phone,
        session_enc=b"0",
        status=status,
        tags=tags,
        is_paused=is_paused,
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


def test_assign_accounts_with_filters_selects_by_status_and_tags():
    session = TestingSession()
    try:
        project = make_project(session, "filters")
        task = make_task(session, project.id, "Task filters")

        matching_one = make_account(
            session,
            project.id,
            "+72000000001",
            status=AccountStatus.ACTIVE,
            tags="vip,news",
        )
        matching_two = make_account(
            session,
            project.id,
            "+72000000002",
            status=AccountStatus.ACTIVE,
            tags="vip",
        )
        make_account(
            session,
            project.id,
            "+72000000003",
            status=AccountStatus.BANNED,
            tags="vip",
        )
        make_account(
            session,
            project.id,
            "+72000000004",
            status=AccountStatus.ACTIVE,
            tags="news",
        )

        service = TaskService(session)
        summary = service.assign_accounts(
            task.id,
            filters={"status": "ACTIVE", "tags": ["vip"]},
        )

        assert summary.applied == 2
        assert summary.already_linked == 0
        assert summary.requested == 2

        assignments = session.query(TaskAssignment).filter(TaskAssignment.task_id == task.id).all()
        assigned_ids = {assignment.account_id for assignment in assignments}
        assert assigned_ids == {matching_one.id, matching_two.id}
    finally:
        session.close()


def test_assign_accounts_filters_respect_pause_and_limit_and_exclude():
    session = TestingSession()
    try:
        project = make_project(session, "pause")
        task = make_task(session, project.id, "Task pause")

        eligible_one = make_account(
            session,
            project.id,
            "+73000000001",
            status=AccountStatus.ACTIVE,
            is_paused=False,
        )
        make_account(
            session,
            project.id,
            "+73000000002",
            status=AccountStatus.ACTIVE,
            is_paused=True,
        )
        eligible_two = make_account(
            session,
            project.id,
            "+73000000003",
            status=AccountStatus.ACTIVE,
            is_paused=False,
        )

        service = TaskService(session, max_assignments_per_request=5)
        summary = service.assign_accounts(
            task.id,
            filters={
                "status": [AccountStatus.ACTIVE],
                "is_paused": False,
                "exclude_ids": [eligible_one.id],
                "limit": 1,
            },
        )

        assert summary.applied == 1
        assert summary.requested == 1
        assignments = session.query(TaskAssignment).filter(TaskAssignment.task_id == task.id).all()
        assert [assignment.account_id for assignment in assignments] == [eligible_two.id]
    finally:
        session.close()


def test_assign_accounts_invalid_status_filter():
    session = TestingSession()
    try:
        project = make_project(session, "invalid")
        task = make_task(session, project.id, "Task invalid")

        make_account(session, project.id, "+74000000001")

        service = TaskService(session)
        with pytest.raises(InvalidFilter):
            service.assign_accounts(task.id, filters={"status": "UNKNOWN"})
    finally:
        session.close()
