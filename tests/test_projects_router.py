from __future__ import annotations

import os

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models.base import Base
from tgac.api.models.core import Project, ProjectStatus, User, UserRole
from tgac.api.routers.projects import create_project, delete_project, list_projects, update_project
from tgac.api.schemas.projects import ProjectCreateRequest, ProjectUpdateRequest


def setup_module(module):
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
    os.environ.setdefault("BASE_URL", "http://localhost")
    os.environ.setdefault("DB_URL", "sqlite:///:memory:")
    os.environ.setdefault("SESSION_SECRET_KEY", "test-secret")

    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


def fresh_session() -> Session:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


def make_user(session: Session, username: str) -> User:
    user = User(username=username)
    session.add(user)
    session.flush()
    return user


def test_create_and_list_projects_returns_serialized_payload():
    session = fresh_session()
    try:
        user = make_user(session, "alice")

        response = create_project(
            ProjectCreateRequest(user_id=user.id, name="Alpha", status=ProjectStatus.ACTIVE),
            current_user=user,
            db=session,
        )

        assert response.data["name"] == "Alpha"
        assert response.data["status"] == ProjectStatus.ACTIVE.value

        listing = list_projects(current_user=user, db=session)
        assert len(listing.data) == 1
        assert listing.data[0]["id"] == response.data["id"]
    finally:
        session.close()


def test_update_project_changes_name_and_status():
    session = fresh_session()
    try:
        user = make_user(session, "bob")
        created = create_project(
            ProjectCreateRequest(user_id=user.id, name="Bravo", status=ProjectStatus.ACTIVE),
            current_user=user,
            db=session,
        )

        project_id = created.data["id"]

        updated = update_project(
            project_id,
            ProjectUpdateRequest(name="Bravo Updated", status=ProjectStatus.PAUSED),
            current_user=user,
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
    session = fresh_session()
    try:
        user = make_user(session, "carol")
        created = create_project(
            ProjectCreateRequest(user_id=user.id, name="Charlie", status=ProjectStatus.ACTIVE),
            current_user=user,
            db=session,
        )

        project_id = created.data["id"]

        deleted = delete_project(project_id, current_user=user, db=session)
        assert deleted.data == {"id": project_id, "deleted": True}
        assert session.get(Project, project_id) is None
    finally:
        session.close()


def test_create_project_enforces_user_quota():
    session = fresh_session()
    try:
        user = make_user(session, "erin")
        user.quota_projects = 1
        session.flush()

        create_project(
            ProjectCreateRequest(
                user_id=user.id, name="First", status=ProjectStatus.ACTIVE
            ),
            current_user=user,
            db=session,
        )

        try:
            create_project(
                ProjectCreateRequest(
                    user_id=user.id, name="Second", status=ProjectStatus.ACTIVE
                ),
                current_user=user,
                db=session,
            )
        except HTTPException as exc:
            assert exc.status_code == 403
        else:  # pragma: no cover - sanity guard
            raise AssertionError("Expected HTTPException for quota overflow")
    finally:
        session.close()


def test_update_missing_project_raises_not_found():
    session = fresh_session()
    try:
        user = make_user(session, "dave")
        try:
            update_project(999, ProjectUpdateRequest(name="Ghost"), current_user=user, db=session)
        except HTTPException as exc:
            assert exc.status_code == 404
        else:  # pragma: no cover - sanity guard
            raise AssertionError("Expected HTTPException for missing project")
    finally:
        session.close()


def test_list_projects_scoped_by_user_and_admin_can_view_all():
    session = fresh_session()
    try:
        owner = make_user(session, "owner")
        other = make_user(session, "other")

        create_project(
            ProjectCreateRequest(user_id=owner.id, name="Owner", status=ProjectStatus.ACTIVE),
            current_user=owner,
            db=session,
        )
        create_project(
            ProjectCreateRequest(user_id=other.id, name="Other", status=ProjectStatus.ACTIVE),
            current_user=other,
            db=session,
        )

        owner_listing = list_projects(current_user=owner, db=session)
        assert len(owner_listing.data) == 1
        assert owner_listing.data[0]["user_id"] == owner.id

        admin = make_user(session, "admin")
        admin.role = UserRole.ADMIN
        session.flush()

        admin_listing = list_projects(current_user=admin, db=session)
        assert {item["name"] for item in admin_listing.data} == {"Owner", "Other"}
    finally:
        session.close()


def test_non_admin_cannot_access_foreign_project():
    session = TestingSession()
    try:
        owner = make_user(session, "project-owner")
        intruder = make_user(session, "intruder")

        created = create_project(
            ProjectCreateRequest(user_id=owner.id, name="Secret", status=ProjectStatus.ACTIVE),
            current_user=owner,
            db=session,
        )

        with pytest.raises(HTTPException) as update_exc:
            update_project(
                created.data["id"],
                ProjectUpdateRequest(name="Hacked"),
                current_user=intruder,
                db=session,
            )
        assert update_exc.value.status_code == 403

        with pytest.raises(HTTPException) as delete_exc:
            delete_project(created.data["id"], current_user=intruder, db=session)
        assert delete_exc.value.status_code == 403

        with pytest.raises(HTTPException) as create_exc:
            create_project(
                ProjectCreateRequest(user_id=owner.id, name="Another", status=ProjectStatus.ACTIVE),
                current_user=intruder,
                db=session,
            )
        assert create_exc.value.status_code == 403
    finally:
        session.close()
