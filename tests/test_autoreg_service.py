from __future__ import annotations

import os
from datetime import datetime

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from tgac.api.models.base import Base
from tgac.api.models.core import (
    Account,
    AccountStatus,
    Job,
    JobStatus,
    JobType,
    Project,
    User,
)
from tgac.api.services.autoreg import (
    AutoRegService,
    AutoRegServiceError,
    SmsActivation,
    SmsCode,
)
from tgac.api.services.scheduler_core import SchedulerCore


if "SESSION_SECRET_KEY" not in os.environ:
    os.environ["SESSION_SECRET_KEY"] = Fernet.generate_key().decode()

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("BASE_URL", "https://example.com")
os.environ.setdefault("DB_URL", "sqlite:///./autoreg-test.db")


class FakeProvider:
    def __init__(self) -> None:
        self.activation = SmsActivation("act-1", "+10000000001")
        self.request_calls: list[tuple[str, str]] = []
        self.codes: dict[str, SmsCode | None] = {}
        self.finished: list[str] = []
        self.failed: list[tuple[str, str | None]] = []

    def request_number(self, *, service: str, country: str) -> SmsActivation:
        self.request_calls.append((service, country))
        return self.activation

    def fetch_code(self, activation_id: str) -> SmsCode | None:
        return self.codes.get(activation_id)

    def mark_finished(self, activation_id: str) -> None:
        self.finished.append(activation_id)

    def mark_failed(self, activation_id: str, reason: str | None = None) -> None:
        self.failed.append((activation_id, reason))


def create_session() -> tuple[Session, Engine]:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, class_=Session)
    return SessionLocal(), engine


def create_project(session: Session, suffix: str = "base") -> Project:
    user = User(username=f"owner-{suffix}")
    session.add(user)
    session.flush()

    project = Project(user_id=user.id, name=f"Project {suffix}")
    session.add(project)
    session.flush()
    return project


def test_start_registration_creates_job_with_payload():
    session, engine = create_session()
    try:
        project = create_project(session, "start")
        provider = FakeProvider()
        scheduler = SchedulerCore(session)
        service = AutoRegService(
            session, scheduler, provider, poll_interval_seconds=5, max_poll_attempts=3
        )

        job = service.start_registration(
            project.id, country="1", metadata={"tags": "vip"}
        )

        assert job.type == JobType.AUTOREG_STEP
        assert job.payload["state"] == AutoRegService.REQUEST_NUMBER
        assert job.payload["country"] == "1"
        assert job.payload["metadata"] == {"tags": "vip"}
    finally:
        session.close()
        engine.dispose()


def test_process_request_number_schedules_wait_step():
    session, engine = create_session()
    try:
        project = create_project(session, "request")
        provider = FakeProvider()
        scheduler = SchedulerCore(session)
        service = AutoRegService(
            session, scheduler, provider, poll_interval_seconds=5, max_poll_attempts=3
        )

        job = service.start_registration(project.id)
        job = session.get(Job, job.id)
        assert job is not None
        job.status = JobStatus.RUNNING
        session.commit()

        result = service.process_job(job)

        assert result.success is True
        assert provider.request_calls == [("tg", "0")]
        follow_up = session.query(Job).filter(Job.id != job.id).one()
        assert follow_up.payload["state"] == AutoRegService.WAIT_FOR_CODE
        assert follow_up.payload["activation_id"] == provider.activation.activation_id
    finally:
        session.close()
        engine.dispose()


def test_wait_for_code_without_sms_requeues_job():
    session, engine = create_session()
    try:
        project = create_project(session, "requeue")
        provider = FakeProvider()
        scheduler = SchedulerCore(session)
        service = AutoRegService(
            session, scheduler, provider, poll_interval_seconds=2, max_poll_attempts=3
        )

        job = Job(
            type=JobType.AUTOREG_STEP,
            payload={
                "state": AutoRegService.WAIT_FOR_CODE,
                "project_id": project.id,
                "activation_id": provider.activation.activation_id,
                "phone": provider.activation.phone_number,
                "metadata": {},
                "attempts": 0,
            },
            run_after=datetime.utcnow(),
        )
        session.add(job)
        session.commit()

        job = session.get(Job, job.id)
        assert job is not None
        job.status = JobStatus.RUNNING
        session.commit()

        result = service.process_job(job)

        assert result.success is True
        assert provider.failed == []
        follow_up = session.query(Job).filter(Job.id != job.id).one()
        assert follow_up.payload["attempts"] == 1
        assert follow_up.payload["state"] == AutoRegService.WAIT_FOR_CODE
    finally:
        session.close()
        engine.dispose()


def test_wait_for_code_creates_account_and_marks_finished():
    session, engine = create_session()
    try:
        project = create_project(session, "success")
        provider = FakeProvider()
        scheduler = SchedulerCore(session)
        service = AutoRegService(
            session, scheduler, provider, poll_interval_seconds=2, max_poll_attempts=3
        )

        provider.codes[provider.activation.activation_id] = SmsCode(
            provider.activation.activation_id, "12345"
        )

        job = Job(
            type=JobType.AUTOREG_STEP,
            payload={
                "state": AutoRegService.WAIT_FOR_CODE,
                "project_id": project.id,
                "activation_id": provider.activation.activation_id,
                "phone": provider.activation.phone_number,
                "metadata": {"tags": "warm", "notes": "autoreg"},
                "attempts": 0,
            },
            run_after=datetime.utcnow(),
        )
        session.add(job)
        session.commit()

        job = session.get(Job, job.id)
        assert job is not None
        job.status = JobStatus.RUNNING
        session.commit()

        result = service.process_job(job)

        assert result.success is True
        account = (
            session.query(Account)
            .filter_by(phone=provider.activation.phone_number)
            .one()
        )
        assert account.status == AccountStatus.ACTIVE
        assert account.tags == "warm"
        assert account.notes == "autoreg"
        assert provider.finished == [provider.activation.activation_id]
    finally:
        session.close()
        engine.dispose()


def test_wait_for_code_raises_when_phone_in_other_project():
    session, engine = create_session()
    try:
        project = create_project(session, "target")
        other_project = create_project(session, "other")
        provider = FakeProvider()
        scheduler = SchedulerCore(session)
        service = AutoRegService(
            session, scheduler, provider, poll_interval_seconds=2, max_poll_attempts=3
        )

        provider.codes[provider.activation.activation_id] = SmsCode(
            provider.activation.activation_id, "99999"
        )

        conflict_account = Account(
            project_id=other_project.id,
            phone=provider.activation.phone_number,
            session_enc=b"existing",
            status=AccountStatus.ACTIVE,
        )
        session.add(conflict_account)
        session.commit()

        job = Job(
            type=JobType.AUTOREG_STEP,
            payload={
                "state": AutoRegService.WAIT_FOR_CODE,
                "project_id": project.id,
                "activation_id": provider.activation.activation_id,
                "phone": provider.activation.phone_number,
                "metadata": {},
                "attempts": 0,
            },
            run_after=datetime.utcnow(),
        )
        session.add(job)
        session.commit()

        job = session.get(Job, job.id)
        assert job is not None
        job.status = JobStatus.RUNNING
        session.commit()

        with pytest.raises(AutoRegServiceError):
            service.process_job(job)

        assert provider.finished == []
    finally:
        session.close()
        engine.dispose()
