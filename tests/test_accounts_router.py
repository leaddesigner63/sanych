from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models.base import Base
from tgac.api.models.core import Account, AccountStatus, Project, ProjectStatus, User
from tgac.api.routers.accounts import list_accounts


def setup_module(module) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


def make_project(session: Session, username: str, project_name: str) -> Project:
    user = User(username=username)
    session.add(user)
    session.flush()

    project = Project(user_id=user.id, name=project_name, status=ProjectStatus.ACTIVE)
    session.add(project)
    session.flush()
    return project


def make_account(
    session: Session,
    project: Project,
    phone: str,
    *,
    status: AccountStatus = AccountStatus.NEEDS_LOGIN,
    tags: str | None = None,
    is_paused: bool = False,
    proxy_id: int | None = None,
) -> Account:
    account = Account(
        project_id=project.id,
        phone=phone,
        session_enc=b"",
        status=status,
        tags=tags,
        is_paused=is_paused,
        proxy_id=proxy_id,
    )
    session.add(account)
    session.flush()
    return account


def test_list_accounts_applies_filters() -> None:
    session = TestingSession()
    try:
        project_a = make_project(session, "alice", "Alpha")
        project_b = make_project(session, "bob", "Beta")

        primary = make_account(
            session,
            project_a,
            "100",
            status=AccountStatus.ACTIVE,
            tags="vip,priority",
        )
        make_account(
            session,
            project_a,
            "101",
            status=AccountStatus.BANNED,
            tags="vip",
            is_paused=True,
        )
        make_account(
            session,
            project_b,
            "200",
            status=AccountStatus.ACTIVE,
            tags="priority",
        )

        response = list_accounts(
            db=session,
            project_id=project_a.id,
            status=[AccountStatus.ACTIVE],
            tags=["vip"],
            is_paused=False,
            limit=20,
        )

        assert len(response.data) == 1
        assert response.data[0]["id"] == primary.id
        assert response.data[0]["status"] == AccountStatus.ACTIVE.value
    finally:
        session.close()


def test_list_accounts_respects_limit_and_order() -> None:
    session = TestingSession()
    try:
        project = make_project(session, "carol", "Gamma")
        first = make_account(session, project, "300", status=AccountStatus.ACTIVE)
        second = make_account(session, project, "301", status=AccountStatus.ACTIVE)
        third = make_account(session, project, "302", status=AccountStatus.ACTIVE)

        response = list_accounts(db=session, limit=2)

        ids = [item["id"] for item in response.data]
        assert ids == [first.id, second.id]

        response_no_limit = list_accounts(db=session, limit=0)
        all_ids = [item["id"] for item in response_no_limit.data]
        assert all_ids == [first.id, second.id, third.id]
    finally:
        session.close()

