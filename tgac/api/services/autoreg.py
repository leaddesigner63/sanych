from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Protocol

import httpx
from sqlalchemy.orm import Session

from ..models.core import Account, AccountStatus, Job, JobType
from ..utils.crypto import encrypt_session
from ..utils.settings import get_settings
from .scheduler_core import SchedulerCore


class SmsProviderError(Exception):
    """Raised when the SMS provider fails to fulfil a request."""


@dataclass(slots=True)
class SmsActivation:
    activation_id: str
    phone_number: str


@dataclass(slots=True)
class SmsCode:
    activation_id: str
    code: str


class SmsProvider(Protocol):
    """Protocol describing the subset of SMS-Activate API we rely on."""

    def request_number(self, *, service: str, country: str) -> SmsActivation: ...

    def fetch_code(self, activation_id: str) -> SmsCode | None: ...

    def mark_finished(self, activation_id: str) -> None: ...

    def mark_failed(self, activation_id: str, reason: str | None = None) -> None: ...


class SmsActivateClient:
    """Minimal synchronous client for the sms-activate.org handler API."""

    base_url = "https://api.sms-activate.org/stubs/handler_api.php"

    def __init__(
        self, api_key: str, *, http_client: httpx.Client | None = None
    ) -> None:
        self.api_key = api_key
        self._http = http_client or httpx.Client(timeout=10.0)

    def request_number(self, *, service: str, country: str) -> SmsActivation:
        params = {
            "api_key": self.api_key,
            "action": "getNumber",
            "service": service,
            "country": country,
        }
        try:
            response = self._http.get(self.base_url, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network failure path
            raise SmsProviderError(f"Failed to request number: {exc}") from exc

        payload = response.text.strip()
        if payload.startswith("ACCESS_NUMBER"):
            _, activation_id, phone = payload.split(":")
            return SmsActivation(activation_id=activation_id, phone_number=phone)
        if payload == "NO_NUMBERS":
            raise SmsProviderError("No numbers available for requested service")
        raise SmsProviderError(f"Unexpected response from SMS-Activate: {payload}")

    def fetch_code(self, activation_id: str) -> SmsCode | None:
        params = {
            "api_key": self.api_key,
            "action": "getStatus",
            "id": activation_id,
        }
        try:
            response = self._http.get(self.base_url, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network failure path
            raise SmsProviderError(f"Failed to fetch code: {exc}") from exc

        payload = response.text.strip()
        if payload == "STATUS_WAIT_CODE":
            return None
        if payload.startswith("STATUS_OK"):
            _, code = payload.split(":")
            return SmsCode(activation_id=activation_id, code=code)
        if payload in {"STATUS_CANCEL", "STATUS_WAIT_RETRY"}:
            raise SmsProviderError("Activation was cancelled by provider")
        if payload == "NO_ACTIVATION" or payload.startswith("STATUS_ERROR"):
            raise SmsProviderError(f"Failed to fetch code: {payload}")
        return None

    def mark_finished(self, activation_id: str) -> None:
        self._set_status(activation_id, status="6")

    def mark_failed(self, activation_id: str, reason: str | None = None) -> None:
        self._set_status(activation_id, status="8")

    def close(self) -> None:  # pragma: no cover - passthrough
        self._http.close()

    def _set_status(self, activation_id: str, *, status: str) -> None:
        params = {
            "api_key": self.api_key,
            "action": "setStatus",
            "id": activation_id,
            "status": status,
        }
        try:
            response = self._http.get(self.base_url, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network failure path
            raise SmsProviderError(f"Failed to update status: {exc}") from exc

        payload = response.text.strip()
        if payload != "ACCESS_READY":
            raise SmsProviderError(
                f"Unexpected response when updating status: {payload}"
            )


@dataclass(slots=True)
class AutoRegStepResult:
    success: bool
    error: str | None = None
    next_payload: dict | None = None
    delay_seconds: int | None = None
    account_id: int | None = None
    phone: str | None = None


class AutoRegServiceError(Exception):
    """Raised when autoregistration cannot proceed."""


class AutoRegService:
    """State machine that performs Telegram account autoregistration."""

    REQUEST_NUMBER = "REQUEST_NUMBER"
    WAIT_FOR_CODE = "WAIT_FOR_CODE"

    def __init__(
        self,
        db: Session,
        scheduler: SchedulerCore,
        sms_provider: SmsProvider,
        *,
        poll_interval_seconds: int | None = None,
        max_poll_attempts: int | None = None,
        session_factory: Callable[[str, str, dict], bytes] | None = None,
    ) -> None:
        self.db = db
        self.scheduler = scheduler
        self.sms_provider = sms_provider

        settings = get_settings()
        self.poll_interval_seconds = (
            poll_interval_seconds or settings.sms_activate_poll_interval_seconds
        )
        self.max_poll_attempts = (
            max_poll_attempts or settings.sms_activate_max_poll_attempts
        )
        self.session_factory = session_factory or self._default_session_factory

    def start_registration(
        self,
        project_id: int,
        *,
        country: str = "0",
        metadata: dict | None = None,
        priority: int = 0,
    ) -> Job:
        payload = {
            "state": self.REQUEST_NUMBER,
            "project_id": project_id,
            "country": country,
            "metadata": metadata or {},
        }
        return self.scheduler.enqueue(JobType.AUTOREG_STEP, payload, priority=priority)

    def process_job(self, job: Job) -> AutoRegStepResult:
        state = job.payload.get("state", self.REQUEST_NUMBER)
        if state == self.REQUEST_NUMBER:
            result = self._handle_request_number(job)
        elif state == self.WAIT_FOR_CODE:
            result = self._handle_wait_for_code(job)
        else:  # pragma: no cover - defensive branch
            raise AutoRegServiceError(f"Unknown autoreg state: {state}")

        if result.next_payload is not None:
            delay = result.delay_seconds or self.poll_interval_seconds
            run_after = datetime.utcnow() + timedelta(seconds=delay)
            self.scheduler.enqueue(
                JobType.AUTOREG_STEP,
                result.next_payload,
                run_after=run_after,
                priority=job.priority,
            )
        return result

    def _handle_request_number(self, job: Job) -> AutoRegStepResult:
        project_id = self._require(job.payload, "project_id")
        country = job.payload.get("country", "0")
        try:
            activation = self.sms_provider.request_number(service="tg", country=country)
        except SmsProviderError as exc:
            return AutoRegStepResult(False, error=str(exc))

        next_payload = {
            "state": self.WAIT_FOR_CODE,
            "project_id": project_id,
            "activation_id": activation.activation_id,
            "phone": activation.phone_number,
            "metadata": job.payload.get("metadata", {}),
            "attempts": 0,
        }
        return AutoRegStepResult(
            True, next_payload=next_payload, phone=activation.phone_number
        )

    def _handle_wait_for_code(self, job: Job) -> AutoRegStepResult:
        project_id = self._require(job.payload, "project_id")
        activation_id = self._require(job.payload, "activation_id")
        phone = self._require(job.payload, "phone")
        attempts = int(job.payload.get("attempts", 0))
        metadata = job.payload.get("metadata", {})

        try:
            code = self.sms_provider.fetch_code(activation_id)
        except SmsProviderError as exc:
            return AutoRegStepResult(False, error=str(exc))

        if code is None:
            attempts += 1
            if attempts >= self.max_poll_attempts:
                self.sms_provider.mark_failed(activation_id, reason="timeout")
                return AutoRegStepResult(False, error="SMS code not received in time")

            next_payload = job.payload.copy()
            next_payload["attempts"] = attempts
            return AutoRegStepResult(
                True,
                next_payload=next_payload,
                delay_seconds=self.poll_interval_seconds,
            )

        raw_session = self.session_factory(phone, code.code, metadata)
        encrypted_session = encrypt_session(raw_session)

        account = self._upsert_account(project_id, phone, encrypted_session, metadata)
        self.db.commit()

        try:
            self.sms_provider.mark_finished(activation_id)
        except SmsProviderError as exc:
            return AutoRegStepResult(
                False, error=str(exc), account_id=account.id, phone=phone
            )

        return AutoRegStepResult(True, account_id=account.id, phone=phone)

    def _upsert_account(
        self,
        project_id: int,
        phone: str,
        session_enc: bytes,
        metadata: dict,
    ) -> Account:
        account = self.db.query(Account).filter_by(phone=phone).one_or_none()
        if account and account.project_id != project_id:
            raise AutoRegServiceError(
                "Account phone already attached to another project"
            )

        if not account:
            account = Account(
                project_id=project_id,
                phone=phone,
                session_enc=session_enc,
                status=AccountStatus.ACTIVE,
            )
            self.db.add(account)
            self.db.flush()
        else:
            account.session_enc = session_enc
            account.status = AccountStatus.ACTIVE

        if "tags" in metadata:
            account.tags = metadata["tags"]
        if "notes" in metadata:
            account.notes = metadata["notes"]
        if "proxy_id" in metadata:
            account.proxy_id = metadata["proxy_id"]

        return account

    @staticmethod
    def _require(payload: dict, key: str) -> int | str:
        if key not in payload:
            raise AutoRegServiceError(f"Job payload missing required field: {key}")
        return payload[key]

    @staticmethod
    def _default_session_factory(
        phone: str, code: str, metadata: dict
    ) -> bytes:  # pragma: no cover - deterministic helper
        seed = metadata.get("seed", "")
        token = f"{phone}:{code}:{seed}".encode()
        return token


__all__ = [
    "AutoRegService",
    "AutoRegServiceError",
    "AutoRegStepResult",
    "SmsActivateClient",
    "SmsActivation",
    "SmsCode",
    "SmsProvider",
    "SmsProviderError",
]
