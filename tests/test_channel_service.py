from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models import core  # noqa: F401
from tgac.api.models.base import Base
from tgac.api.models.core import Account, AccountStatus, Channel, Project, User
from tgac.api.services.channels import (
    ChannelLimitExceeded,
    ChannelService,
    ProjectMismatch,
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


def make_channel(session: Session, project_id: int, title: str) -> Channel:
    channel = Channel(project_id=project_id, title=title, active=True)
    session.add(channel)
    session.flush()
    return channel


def test_assign_accounts_enforces_limit():
    session = TestingSession()
    try:
        project = make_project(session, "limit")
        account = make_account(session, project.id, "+30000000001")
        c1 = make_channel(session, project.id, "Channel 1")
        c2 = make_channel(session, project.id, "Channel 2")
        c3 = make_channel(session, project.id, "Channel 3")

        service = ChannelService(session, max_channels_per_account=2)

        service.assign_accounts(c1.id, [account.id])
        service.assign_accounts(c2.id, [account.id])

        try:
            service.assign_accounts(c3.id, [account.id])
        except ChannelLimitExceeded:
            session.rollback()
        else:  # pragma: no cover - sanity branch
            raise AssertionError("Channel limit should have been enforced")
    finally:
        session.close()


def test_assign_accounts_requires_same_project():
    session = TestingSession()
    try:
        project = make_project(session, "primary")
        other_project = make_project(session, "other")

        account = make_account(session, other_project.id, "+40000000001")
        channel = make_channel(session, project.id, "Channel main")

        service = ChannelService(session, max_channels_per_account=5)

        try:
            service.assign_accounts(channel.id, [account.id])
        except ProjectMismatch:
            session.rollback()
        else:  # pragma: no cover - sanity branch
            raise AssertionError("Project mismatch should raise an error")
    finally:
        session.close()


def test_assign_accounts_idempotent():
    session = TestingSession()
    try:
        project = make_project(session, "idem")
        account = make_account(session, project.id, "+50000000001")
        channel = make_channel(session, project.id, "Channel I")

        service = ChannelService(session, max_channels_per_account=3)

        first = service.assign_accounts(channel.id, [account.id])
        assert len(first) == 1

        second = service.assign_accounts(channel.id, [account.id])
        assert len(second) == 0
    finally:
        session.close()
