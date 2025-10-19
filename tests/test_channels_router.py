from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models.base import Base
from tgac.api.models.core import Channel, Project, ProjectStatus, User
from tgac.api.routers.channels import list_channels


def setup_module(module) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


def teardown_module(module) -> None:
    module.engine.dispose()


def make_project(session: Session, username: str, project_name: str) -> Project:
    user = User(username=username)
    session.add(user)
    session.flush()

    project = Project(user_id=user.id, name=project_name, status=ProjectStatus.ACTIVE)
    session.add(project)
    session.flush()
    return project


def make_channel(session: Session, project: Project, title: str, username: str | None = None) -> Channel:
    channel = Channel(
        project_id=project.id,
        title=title,
        username=username,
        active=True,
    )
    session.add(channel)
    session.flush()
    return channel


def test_list_channels_filters_by_project() -> None:
    session = TestingSession()
    try:
        project_a = make_project(session, "alice", "Alpha")
        project_b = make_project(session, "bob", "Beta")

        channel_a = make_channel(session, project_a, "Alpha News", username="alpha")
        make_channel(session, project_b, "Beta News", username="beta")

        response = list_channels(project_id=project_a.id, db=session)

        assert len(response.data) == 1
        assert response.data[0]["id"] == channel_a.id
        assert response.data[0]["project_id"] == project_a.id
    finally:
        session.close()


def test_list_channels_respects_limit_and_order() -> None:
    session = TestingSession()
    try:
        project = make_project(session, "carol", "Gamma")
        first = make_channel(session, project, "First", username="first")
        second = make_channel(session, project, "Second", username="second")
        third = make_channel(session, project, "Third", username="third")

        limited = list_channels(db=session, limit=2)
        limited_ids = [item["id"] for item in limited.data]
        assert limited_ids == [third.id, second.id]

        unlimited = list_channels(db=session, limit=0)
        unlimited_ids = [item["id"] for item in unlimited.data]
        assert unlimited_ids == [third.id, second.id, first.id]
    finally:
        session.close()

