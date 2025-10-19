from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models.base import Base
from tgac.api.models.core import Playlist, Project, ProjectStatus, User
from tgac.api.routers.playlists import list_playlists


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


def make_playlist(session: Session, project: Project, name: str, desc: str | None = None) -> Playlist:
    playlist = Playlist(project_id=project.id, name=name, desc=desc)
    session.add(playlist)
    session.flush()
    return playlist


def test_list_playlists_filters_by_project() -> None:
    session = TestingSession()
    try:
        project_a = make_project(session, "alice", "Alpha")
        project_b = make_project(session, "bob", "Beta")

        playlist_a = make_playlist(session, project_a, "Warm", desc="Warm up")
        make_playlist(session, project_b, "Cold", desc="Cold start")

        response = list_playlists(project_id=project_a.id, db=session)

        assert len(response.data) == 1
        assert response.data[0]["id"] == playlist_a.id
        assert response.data[0]["project_id"] == project_a.id
    finally:
        session.close()


def test_list_playlists_respects_limit_and_order() -> None:
    session = TestingSession()
    try:
        project = make_project(session, "carol", "Gamma")
        first = make_playlist(session, project, "First")
        second = make_playlist(session, project, "Second")
        third = make_playlist(session, project, "Third")

        limited = list_playlists(db=session, limit=2)
        limited_ids = [item["id"] for item in limited.data]
        assert limited_ids == [third.id, second.id]

        unlimited = list_playlists(db=session, limit=0)
        unlimited_ids = [item["id"] for item in unlimited.data]
        assert unlimited_ids == [third.id, second.id, first.id]
    finally:
        session.close()

