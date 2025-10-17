from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models import core  # noqa: F401
from tgac.api.models.base import Base
from tgac.api.models.core import Account, AccountStatus, Project, Proxy, ProxyScheme, User
from tgac.api.services.accounts import AccountImportData, AccountService, ProxyLimitExceeded, ProjectMismatch


def setup_module(module):
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


def make_fixtures(session: Session, suffix: str) -> tuple[User, Project, Proxy]:
    user = User(username=f"owner-{suffix}")
    session.add(user)
    session.flush()

    project = Project(user_id=user.id, name=f"Demo-{suffix}")
    session.add(project)
    session.flush()

    proxy = Proxy(
        project_id=project.id,
        name=f"proxy-{suffix}",
        scheme=ProxyScheme.HTTP,
        host="127.0.0.1",
        port=8080,
    )
    session.add(proxy)
    session.flush()

    return user, project, proxy


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


def test_assign_proxy_enforces_limit():
    session = TestingSession()
    try:
        _, project, proxy = make_fixtures(session, "limit")
        service = AccountService(session)

        a1 = make_account(session, project.id, "+10000000001")
        a2 = make_account(session, project.id, "+10000000002")
        a3 = make_account(session, project.id, "+10000000003")
        a4 = make_account(session, project.id, "+10000000004")

        service.assign_proxy(a1.id, proxy.id)
        service.assign_proxy(a2.id, proxy.id)
        service.assign_proxy(a3.id, proxy.id)

        # already assigned account can keep its proxy
        service.assign_proxy(a3.id, proxy.id)

        try:
            service.assign_proxy(a4.id, proxy.id)
        except ProxyLimitExceeded:
            session.rollback()
        else:  # pragma: no cover - sanity branch
            raise AssertionError("Proxy limit should have been enforced")
    finally:
        session.close()


def test_assign_proxy_requires_same_project():
    session = TestingSession()
    try:
        _, project, proxy = make_fixtures(session, "mismatch")
        service = AccountService(session)

        other_user = User(username="other-mismatch")
        session.add(other_user)
        session.flush()

        other_project = Project(user_id=other_user.id, name="Other")
        session.add(other_project)
        session.flush()

        account = make_account(session, other_project.id, "+20000000001")

        try:
            service.assign_proxy(account.id, proxy.id)
        except ProjectMismatch:
            session.rollback()
        else:  # pragma: no cover - sanity branch
            raise AssertionError("Project mismatch should raise an error")
    finally:
        session.close()


def test_import_accounts_skips_duplicates_and_existing():
    session = TestingSession()
    try:
        _, project, _ = make_fixtures(session, "import")
        service = AccountService(session)

        make_account(session, project.id, "+30000000001")

        summary = service.import_accounts(
            project.id,
            [
                AccountImportData(phone="+30000000001", status=AccountStatus.ACTIVE),
                AccountImportData(phone="+30000000002", tags="vip"),
                AccountImportData(phone="+30000000002"),
            ],
        )

        assert [account.phone for account in summary.created] == ["+30000000002"]
        assert summary.skipped == ["+30000000001", "+30000000002"]
    finally:
        session.close()


def test_record_healthcheck_updates_status_and_notes():
    session = TestingSession()
    try:
        _, project, _ = make_fixtures(session, "health")
        service = AccountService(session)

        account = make_account(session, project.id, "+40000000001")
        assert account.last_health_at is None

        updated = service.record_healthcheck(
            account.id,
            status=AccountStatus.ACTIVE,
            notes="ok",
        )

        assert updated.last_health_at is not None
        assert updated.status == AccountStatus.ACTIVE
        assert updated.notes == "ok"
    finally:
        session.close()


def test_set_paused_toggles_flag():
    session = TestingSession()
    try:
        _, project, _ = make_fixtures(session, "pause")
        service = AccountService(session)

        account = make_account(session, project.id, "+50000000001")
        assert account.is_paused is False

        paused = service.set_paused(account.id, True)
        assert paused.is_paused is True

        resumed = service.set_paused(account.id, False)
        assert resumed.is_paused is False
    finally:
        session.close()
