from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models.base import Base
from tgac.api.models.core import Project, ProjectStatus, User
from tgac.api.routers.projects import create_project, delete_project, list_projects, update_project
from tgac.api.schemas.projects import ProjectCreateRequest, ProjectUpdateRequest


def setup_module(module):
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


def make_user(session: Session, username: str) -> User:
    user = User(username=username)
    session.add(user)
    session.flush()
    return user


def test_create_and_list_projects_returns_serialized_payload():
    session = TestingSession()
    try:
        user = make_user(session, "alice")

        response = create_project(
            ProjectCreateRequest(user_id=user.id, name="Alpha", status=ProjectStatus.ACTIVE),
            db=session,
        )

        assert response.data["name"] == "Alpha"
        assert response.data["status"] == ProjectStatus.ACTIVE.value

        listing = list_projects(db=session)
        assert len(listing.data) == 1
        assert listing.data[0]["id"] == response.data["id"]
    finally:
        session.close()


def test_update_project_changes_name_and_status():
    session = TestingSession()
    try:
        user = make_user(session, "bob")
        created = create_project(
            ProjectCreateRequest(user_id=user.id, name="Bravo", status=ProjectStatus.ACTIVE),
            db=session,
        )

        project_id = created.data["id"]

        updated = update_project(
            project_id,
            ProjectUpdateRequest(name="Bravo Updated", status=ProjectStatus.PAUSED),
            db=session,
        )

        assert updated.data["name"] == "Bravo Updated"
        assert updated.data["status"] == ProjectStatus.PAUSED.value

        project = session.get(Project, project_id)
        assert project is not None
        assert project.name == "Bravo Updated"
        assert project.status == ProjectStatus.PAUSED
    finally:
        session.close()


def test_delete_project_removes_row():
    session = TestingSession()
    try:
        user = make_user(session, "carol")
        created = create_project(
            ProjectCreateRequest(user_id=user.id, name="Charlie", status=ProjectStatus.ACTIVE),
            db=session,
        )

        project_id = created.data["id"]

        deleted = delete_project(project_id, db=session)
        assert deleted.data == {"id": project_id, "deleted": True}
        assert session.get(Project, project_id) is None
    finally:
        session.close()


def test_create_project_enforces_user_quota():
    session = TestingSession()
    try:
        user = make_user(session, "erin")
        user.quota_projects = 1
        session.flush()

        create_project(
            ProjectCreateRequest(
                user_id=user.id, name="First", status=ProjectStatus.ACTIVE
            ),
            db=session,
        )

        try:
            create_project(
                ProjectCreateRequest(
                    user_id=user.id, name="Second", status=ProjectStatus.ACTIVE
                ),
                db=session,
            )
        except HTTPException as exc:
            assert exc.status_code == 403
        else:  # pragma: no cover - sanity guard
            raise AssertionError("Expected HTTPException for quota overflow")
    finally:
        session.close()


def test_update_missing_project_raises_not_found():
    session = TestingSession()
    try:
        make_user(session, "dave")
        try:
            update_project(999, ProjectUpdateRequest(name="Ghost"), db=session)
        except HTTPException as exc:
            assert exc.status_code == 404
        else:  # pragma: no cover - sanity guard
            raise AssertionError("Expected HTTPException for missing project")
    finally:
        session.close()
