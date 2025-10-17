"""Business logic helpers for account management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from sqlalchemy.orm import Session

from ..models.core import Account, AccountStatus, Proxy

MAX_ACCOUNTS_PER_PROXY = 3


class AccountServiceError(Exception):
    """Base error for account service failures."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class AccountNotFound(AccountServiceError):
    """Raised when an account cannot be located."""


class ProxyNotFound(AccountServiceError):
    """Raised when a proxy cannot be located."""


class ProjectMismatch(AccountServiceError):
    """Raised when entities belong to different projects."""


class ProxyLimitExceeded(AccountServiceError):
    """Raised when a proxy already serves the allowed number of accounts."""


@dataclass(frozen=True)
class AccountImportData:
    """Lightweight container describing a single account to be imported."""

    phone: str
    status: AccountStatus = AccountStatus.NEEDS_LOGIN
    tags: str | None = None
    notes: str | None = None


@dataclass
class ImportSummary:
    """Information about the outcome of a bulk import operation."""

    created: list[Account]
    skipped: list[str]


@dataclass
class AccountService:
    """Encapsulates account-related domain operations."""

    db: Session

    def assign_proxy(self, account_id: int, proxy_id: int) -> Account:
        """Assign a proxy to the account while enforcing constraints."""

        account = self.db.get(Account, account_id)
        if account is None:
            raise AccountNotFound(f"Account {account_id} not found", status_code=404)

        proxy = self.db.get(Proxy, proxy_id)
        if proxy is None:
            raise ProxyNotFound(f"Proxy {proxy_id} not found", status_code=404)

        if account.project_id != proxy.project_id:
            raise ProjectMismatch("Account and proxy must belong to the same project")

        if account.proxy_id == proxy_id:
            return account

        assignments = (
            self.db.query(Account)
            .filter(Account.proxy_id == proxy_id, Account.id != account_id)
            .count()
        )
        if assignments >= MAX_ACCOUNTS_PER_PROXY:
            raise ProxyLimitExceeded(
                f"Proxy {proxy_id} already has {MAX_ACCOUNTS_PER_PROXY} accounts assigned"
            )

        account.proxy_id = proxy_id
        self.db.commit()
        self.db.refresh(account)
        return account

    def import_accounts(self, project_id: int, entries: Sequence[AccountImportData]) -> ImportSummary:
        """Create accounts in bulk while avoiding duplicates."""

        if not entries:
            return ImportSummary(created=[], skipped=[])

        phones = [entry.phone for entry in entries]
        existing = {
            phone
            for (phone,) in self.db.query(Account.phone).filter(Account.phone.in_(phones)).all()
        }

        created: list[Account] = []
        skipped: list[str] = []
        seen: set[str] = set()

        for entry in entries:
            if entry.phone in seen:
                skipped.append(entry.phone)
                continue
            seen.add(entry.phone)

            if entry.phone in existing:
                skipped.append(entry.phone)
                continue

            account = Account(
                project_id=project_id,
                phone=entry.phone,
                session_enc=b"",
                status=entry.status,
                tags=entry.tags,
                notes=entry.notes,
            )
            self.db.add(account)
            created.append(account)

        if created:
            self.db.commit()
            for account in created:
                self.db.refresh(account)
        else:
            self.db.flush()

        return ImportSummary(created=created, skipped=skipped)

    def record_healthcheck(
        self, account_id: int, *, status: AccountStatus | None = None, notes: str | None = None
    ) -> Account:
        """Persist the outcome of an account health check."""

        account = self.db.get(Account, account_id)
        if account is None:
            raise AccountNotFound(f"Account {account_id} not found", status_code=404)

        account.last_health_at = datetime.utcnow()
        if status is not None:
            account.status = status
        if notes is not None:
            account.notes = notes

        self.db.commit()
        self.db.refresh(account)
        return account

    def set_paused(self, account_id: int, paused: bool) -> Account:
        """Toggle the paused flag for the given account."""

        account = self.db.get(Account, account_id)
        if account is None:
            raise AccountNotFound(f"Account {account_id} not found", status_code=404)

        account.is_paused = paused
        self.db.commit()
        self.db.refresh(account)
        return account


__all__ = [
    "AccountService",
    "AccountServiceError",
    "AccountNotFound",
    "ProxyNotFound",
    "ProjectMismatch",
    "ProxyLimitExceeded",
    "AccountImportData",
    "ImportSummary",
    "MAX_ACCOUNTS_PER_PROXY",
]
