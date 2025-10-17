from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models.base import Base
from tgac.api.models.core import Project, User
from tgac.api.services.settings import (
    InvalidSettingValue,
    SettingsService,
    UnknownSetting,
)

DEFAULTS = {
    "MAX_CHANNELS_PER_ACCOUNT": 50,
    "COMMENT_COLLISION_LIMIT_PER_POST": 1,
    "MAX_ACTIVE_THREADS_PER_ACCOUNT": 50,
    "COMMENT_VISIBILITY_STALE_MINUTES": 5,
}


def setup_module(module):
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


def create_project(session: Session, username: str = "owner") -> Project:
    user = User(username=username)
    session.add(user)
    session.flush()

    project = Project(user_id=user.id, name=f"Project-{username}")
    session.add(project)
    session.flush()

    return project


def test_describe_merges_defaults_and_overrides():
    session = TestingSession()
    try:
        project = create_project(session, "defaults")
        service = SettingsService(session, defaults=DEFAULTS)

        service.set_value("MAX_ACTIVE_THREADS_PER_ACCOUNT", 80)
        service.set_value("MAX_CHANNELS_PER_ACCOUNT", 40, project.id)

        description = service.describe(project.id)

        assert description["defaults"]["MAX_ACTIVE_THREADS_PER_ACCOUNT"] == 50
        assert description["effective"]["MAX_ACTIVE_THREADS_PER_ACCOUNT"] == 80
        assert description["effective"]["MAX_CHANNELS_PER_ACCOUNT"] == 40

        scopes = {item["scope"] for item in description["overrides"]}
        assert scopes == {"global", "project"}
    finally:
        session.close()


def test_set_value_validates_input_type():
    session = TestingSession()
    try:
        service = SettingsService(session, defaults=DEFAULTS)
        try:
            service.set_value("MAX_CHANNELS_PER_ACCOUNT", "abc")
        except InvalidSettingValue:
            session.rollback()
        else:  # pragma: no cover - sanity
            raise AssertionError("Expected InvalidSettingValue")
    finally:
        session.close()


def test_unknown_key_rejected():
    session = TestingSession()
    try:
        service = SettingsService(session, defaults=DEFAULTS)
        try:
            service.set_value("UNKNOWN_KEY", 1)
        except UnknownSetting:
            session.rollback()
        else:  # pragma: no cover - sanity
            raise AssertionError("Expected UnknownSetting error")
    finally:
        session.close()


def test_delete_value_restores_effective_default():
    session = TestingSession()
    try:
        project = create_project(session, "remove")
        service = SettingsService(session, defaults=DEFAULTS)

        service.set_value("COMMENT_COLLISION_LIMIT_PER_POST", 2, project.id)
        before = service.get_effective(project.id)["COMMENT_COLLISION_LIMIT_PER_POST"]
        assert before == 2

        removed = service.delete_value("COMMENT_COLLISION_LIMIT_PER_POST", project.id)
        assert removed is True

        after = service.get_effective(project.id)["COMMENT_COLLISION_LIMIT_PER_POST"]
        assert after == DEFAULTS["COMMENT_COLLISION_LIMIT_PER_POST"]
    finally:
        session.close()
