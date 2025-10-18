from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models.base import Base
from tgac.api.routers.audit import create_audit_entry, list_audit_entries
from tgac.api.schemas.audit import AuditLogCreateRequest
from tgac.api.services.audit import AuditLogService


def setup_module(module):
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


def teardown_module(module):
    module.engine.dispose()


def test_create_audit_entry_returns_serialized_payload():
    session = TestingSession()
    try:
        payload = AuditLogCreateRequest(actor="alice", action="login", meta={"ip": "1.1.1.1"})
        response = create_audit_entry(payload, db=session)

        assert response.data["actor"] == "alice"
        assert response.data["action"] == "login"
        assert response.data["meta"] == {"ip": "1.1.1.1"}
        assert "ts" in response.data
    finally:
        session.close()


def test_list_audit_entries_supports_cursor():
    session = TestingSession()
    try:
        service = AuditLogService(session)
        for idx in range(3):
            service.record(f"user-{idx}", "action", {"index": idx})

        first_page = list_audit_entries(limit=2, db=session)
        assert first_page.data["count"] == 2
        next_cursor = first_page.data["next_cursor"]
        assert next_cursor is not None

        second_page = list_audit_entries(limit=2, cursor=next_cursor, db=session)
        ids_first = [item["id"] for item in first_page.data["items"]]
        ids_second = [item["id"] for item in second_page.data["items"]]
        if ids_second:
            assert max(ids_second) < min(ids_first)
    finally:
        session.close()


def test_list_audit_entries_rejects_invalid_limit():
    session = TestingSession()
    try:
        try:
            list_audit_entries(limit=0, db=session)
        except HTTPException as exc:
            assert exc.status_code == 422
        else:  # pragma: no cover - sanity guard
            raise AssertionError("Expected HTTPException for invalid limit")
    finally:
        session.close()

