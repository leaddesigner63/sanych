from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models.base import Base
from tgac.api.models.core import AuditLog
from tgac.api.services.audit import AuditLogService, InvalidLimit


def setup_module(module):
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


def teardown_module(module):
    module.engine.dispose()


def test_record_persists_entry():
    session = TestingSession()
    try:
        service = AuditLogService(session)
        entry = service.record("alice", "login", {"ip": "127.0.0.1"})

        assert entry.id > 0
        stored = session.get(AuditLog, entry.id)
        assert stored is not None
        assert stored.actor == "alice"
        assert stored.action == "login"
        assert stored.meta == {"ip": "127.0.0.1"}
    finally:
        session.close()


def test_list_recent_returns_window_with_cursor():
    session = TestingSession()
    try:
        service = AuditLogService(session)
        for idx in range(5):
            service.record(f"user-{idx}", "action", {"index": idx})

        window = service.list_recent(limit=2)
        assert len(window.items) == 2
        assert window.items[0].id > window.items[1].id
        assert window.next_cursor == window.items[-1].id

        next_window = service.list_recent(limit=2, cursor=window.next_cursor)
        assert all(item.id < window.items[-1].id for item in next_window.items)
    finally:
        session.close()


def test_invalid_limit_raises_error():
    session = TestingSession()
    try:
        service = AuditLogService(session)
        try:
            service.list_recent(limit=0)
        except InvalidLimit as exc:
            assert exc.status_code == 422
        else:  # pragma: no cover - sanity branch
            raise AssertionError("Expected InvalidLimit error")
    finally:
        session.close()

