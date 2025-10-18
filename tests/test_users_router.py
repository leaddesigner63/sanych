from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models.base import Base
from tgac.api.models.core import User, UserRole
from tgac.api.routers.users import block_user, create_user, list_users, update_user
from tgac.api.schemas.users import UserCreateRequest, UserUpdateRequest


def setup_module(module):
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


def teardown_module(module):
    module.engine.dispose()


def test_create_and_list_users_returns_full_payload():
    session = TestingSession()
    try:
        created = create_user(
            UserCreateRequest(username="alice", role=UserRole.ADMIN, quota_projects=5),
            db=session,
        )

        assert created.data["username"] == "alice"
        assert created.data["role"] == UserRole.ADMIN.value
        assert created.data["quota_projects"] == 5
        assert created.data["is_active"] is True
        assert "created_at" in created.data

        listing = list_users(db=session)
        assert len(listing.data) == 1
        assert listing.data[0]["id"] == created.data["id"]
    finally:
        session.close()


def test_update_user_changes_role_quota_and_activation():
    session = TestingSession()
    try:
        created = create_user(UserCreateRequest(username="bob"), db=session)
        user_id = created.data["id"]

        updated = update_user(
            user_id,
            UserUpdateRequest(role=UserRole.ADMIN, quota_projects=None, is_active=False),
            db=session,
        )

        assert updated.data["role"] == UserRole.ADMIN.value
        assert updated.data["quota_projects"] is None
        assert updated.data["is_active"] is False

        # reactivate via update
        reactivated = update_user(
            user_id,
            UserUpdateRequest(is_active=True, telegram_id=12345),
            db=session,
        )

        assert reactivated.data["is_active"] is True
        assert reactivated.data["telegram_id"] == 12345

        persisted = session.get(User, user_id)
        assert persisted is not None
        assert persisted.role == UserRole.ADMIN
        assert persisted.quota_projects is None
        assert persisted.is_active is True
        assert persisted.telegram_id == 12345
    finally:
        session.close()


def test_block_user_sets_inactive_flag():
    session = TestingSession()
    try:
        created = create_user(UserCreateRequest(username="carol"), db=session)
        user_id = created.data["id"]

        blocked = block_user(user_id, db=session)
        assert blocked.data["is_active"] is False

        model = session.get(User, user_id)
        assert model is not None
        assert model.is_active is False
    finally:
        session.close()


def test_duplicate_username_raises_conflict():
    session = TestingSession()
    try:
        create_user(UserCreateRequest(username="dave"), db=session)
        try:
            create_user(UserCreateRequest(username="dave"), db=session)
        except HTTPException as exc:
            assert exc.status_code == 409
        else:  # pragma: no cover - safety net
            raise AssertionError("Expected HTTPException for duplicate username")
    finally:
        session.close()
