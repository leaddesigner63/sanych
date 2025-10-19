from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models.base import Base
from tgac.api.routers.logs import prune_logs, tail_logs
from tgac.api.services.logs import LogPruneResult


def setup_module(module) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


def teardown_module(module) -> None:
    module.engine.dispose()


def test_tail_logs_reads_requested_lines(monkeypatch, tmp_path) -> None:
    log_file = tmp_path / "app.log"
    log_file.write_text("first\nsecond\nthird\n", encoding="utf-8")

    original_open = open

    def fake_open(  # type: ignore[override]
        path: str,
        mode: str = "r",
        *args: Any,
        encoding: str | None = None,
        **kwargs: Any,
    ):
        if path == "tgac/logs/app.log":
            return original_open(log_file, mode, *args, encoding=encoding, **kwargs)
        return original_open(path, mode, *args, encoding=encoding, **kwargs)

    monkeypatch.setattr("builtins.open", fake_open)

    response = tail_logs(lines=2)
    assert response.data == {"lines": ["second\n", "third\n"]}


def test_prune_logs_uses_service(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class DummyService:
        def __init__(self, db: Session) -> None:
            captured["db"] = db

        def prune(self, retention_days: int | None = None) -> LogPruneResult:
            captured["retention_days"] = retention_days
            return LogPruneResult(
                events_removed=2,
                audit_removed=1,
                cutoff=datetime(2024, 1, 1, tzinfo=timezone.utc),
            )

    def factory(db: Session) -> DummyService:
        service = DummyService(db)
        captured["service"] = service
        return service

    monkeypatch.setattr("tgac.api.routers.logs.LogMaintenanceService", factory)

    session = TestingSession()
    try:
        response = prune_logs(5, db=session)
        assert captured["db"] is session
        assert captured["retention_days"] == 5
        assert response.data["events_removed"] == 2
        assert response.data["audit_removed"] == 1
        assert response.data["cutoff"].startswith("2024-01-01T00:00:00")
    finally:
        session.close()

