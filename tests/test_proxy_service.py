from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models import core  # noqa: F401
from tgac.api.models.base import Base
from tgac.api.models.core import Project, Proxy, ProxyScheme, User
from tgac.api.services.proxies import (
    ProxyCreateData,
    ProxyImportData,
    ProxyNameExists,
    ProxyNotFound,
    ProxyService,
)


def setup_module(module):
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


def make_project(session: Session, suffix: str) -> tuple[User, Project]:
    user = User(username=f"owner-{suffix}")
    session.add(user)
    session.flush()

    project = Project(user_id=user.id, name=f"Project-{suffix}")
    session.add(project)
    session.flush()
    return user, project


def make_proxy(
    session: Session,
    project_id: int,
    name: str,
    *,
    is_working: bool = True,
    last_check_at: datetime | None = None,
) -> Proxy:
    proxy = Proxy(
        project_id=project_id,
        name=name,
        scheme=ProxyScheme.HTTP,
        host="127.0.0.1",
        port=8080,
        is_working=is_working,
        last_check_at=last_check_at,
    )
    session.add(proxy)
    session.flush()
    return proxy


def test_create_proxy_enforces_unique_name():
    session = TestingSession()
    try:
        _, project = make_project(session, "unique")
        service = ProxyService(session)

        service.create_proxy(
            ProxyCreateData(
                project_id=project.id,
                name="alpha",
                scheme=ProxyScheme.HTTP,
                host="10.0.0.1",
                port=3128,
            )
        )

        with pytest.raises(ProxyNameExists):
            service.create_proxy(
                ProxyCreateData(
                    project_id=project.id,
                    name="alpha",
                    scheme=ProxyScheme.SOCKS5,
                    host="10.0.0.2",
                    port=1080,
                )
            )
    finally:
        session.close()


def test_import_proxies_skips_duplicates_and_existing():
    session = TestingSession()
    try:
        _, project = make_project(session, "import")
        service = ProxyService(session)

        make_proxy(session, project.id, "existing")

        summary = service.import_proxies(
            project.id,
            [
                ProxyImportData(
                    name="existing",
                    scheme=ProxyScheme.HTTP,
                    host="10.0.0.3",
                    port=8000,
                ),
                ProxyImportData(
                    name="beta",
                    scheme=ProxyScheme.SOCKS5,
                    host="10.0.0.4",
                    port=9050,
                ),
                ProxyImportData(
                    name="beta",
                    scheme=ProxyScheme.HTTP,
                    host="10.0.0.5",
                    port=8080,
                ),
            ],
        )

        assert [proxy.name for proxy in summary.created] == ["beta"]
        assert summary.skipped == ["existing", "beta"]
    finally:
        session.close()


def test_record_check_updates_state_and_timestamp():
    session = TestingSession()
    try:
        _, project = make_project(session, "check")
        service = ProxyService(session)

        proxy = make_proxy(
            session,
            project.id,
            "gamma",
            is_working=False,
            last_check_at=datetime.utcnow() - timedelta(days=1),
        )

        updated = service.record_check(proxy.id, is_working=True)
        assert updated.is_working is True
        assert updated.last_check_at is not None
        assert updated.last_check_at >= datetime.utcnow() - timedelta(seconds=5)

        with pytest.raises(ProxyNotFound):
            service.record_check(proxy.id + 999, is_working=False)
    finally:
        session.close()
