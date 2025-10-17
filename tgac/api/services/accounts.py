"""Business logic helpers for account management."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..models.core import Account, Proxy

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


__all__ = [
    "AccountService",
    "AccountServiceError",
    "AccountNotFound",
    "ProxyNotFound",
    "ProjectMismatch",
    "ProxyLimitExceeded",
    "MAX_ACCOUNTS_PER_PROXY",
]
