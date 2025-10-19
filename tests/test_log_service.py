from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models.base import Base
from tgac.api.models.core import AuditLog
from tgac.api.services.logs import LogMaintenanceService
from tgac.api.utils import settings as settings_module


def setup_module(module) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, class_=Session)
    Base.metadata.create_all(engine)

    module.engine = engine
    module.TestingSession = TestingSession


def teardown_module(module) -> None:
    module.engine.dispose()


def _write_event(path: Path, timestamp: datetime, payload: str) -> None:
    record = {"timestamp": timestamp.isoformat(), "payload": payload}
    with path.open("a", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False)
        handle.write("\n")


def test_prune_removes_stale_audit_and_event_entries(monkeypatch, tmp_path) -> None:
    events_path = tmp_path / "events.jsonl"

    now = datetime.now(timezone.utc)
    stale_ts = now - timedelta(days=10)
    fresh_ts = now - timedelta(days=2)

    _write_event(events_path, stale_ts, "stale")
    _write_event(events_path, fresh_ts, "fresh")

    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("BASE_URL", "https://example.test")
    monkeypatch.setenv("DB_URL", "sqlite:///:memory:")
    monkeypatch.setenv("SESSION_SECRET_KEY", "secret-key")

    session = TestingSession()
    try:
        session.add_all(
            [
                AuditLog(actor="old", action="login", meta={}, ts=stale_ts),
                AuditLog(actor="new", action="login", meta={}, ts=fresh_ts),
            ]
        )
        session.commit()

        service = LogMaintenanceService(session, events_path=events_path)
        result = service.prune(retention_days=7)

        assert result.events_removed == 1
        assert result.audit_removed == 1
        assert isinstance(result.cutoff, datetime)

        remaining_lines = events_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(remaining_lines) == 1
        remaining_payload = json.loads(remaining_lines[0])
        assert remaining_payload["payload"] == "fresh"

        remaining_audit = session.query(AuditLog).count()
        assert remaining_audit == 1
    finally:
        session.close()
        settings_module.get_settings.cache_clear()

