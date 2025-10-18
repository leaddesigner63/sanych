from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models.base import Base
from tgac.api.models.core import ProjectStatus, User
from tgac.api.services.projects import (
    ProjectQuotaExceeded,
    ProjectService,
)


def setup_module(module):
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


def teardown_module(module):
    module.engine.dispose()


def make_user(session: Session, username: str, quota: int | None = None) -> User:
    user = User(username=username, quota_projects=quota)
    session.add(user)
    session.flush()
    return user


def test_service_respects_default_quota_when_user_has_none():
    session = TestingSession()
    try:
        settings = SimpleNamespace(default_project_quota=1)
        service = ProjectService(session, settings=settings)

        user = make_user(session, "frank")

        project = service.create_project(
            user_id=user.id, name="Solo", status=ProjectStatus.ACTIVE
        )
        assert project.name == "Solo"

        with pytest.raises(ProjectQuotaExceeded):
            service.create_project(
                user_id=user.id, name="Overflow", status=ProjectStatus.ACTIVE
            )
    finally:
        session.close()


def test_zero_default_quota_allows_unlimited_projects():
    session = TestingSession()
    try:
        settings = SimpleNamespace(default_project_quota=0)
        service = ProjectService(session, settings=settings)

        user = make_user(session, "gary")

        created = []
        for idx in range(3):
            created.append(
                service.create_project(
                    user_id=user.id,
                    name=f"Project {idx}",
                    status=ProjectStatus.ACTIVE,
                )
            )

        assert len(created) == 3
    finally:
        session.close()
