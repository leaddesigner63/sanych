"""Domain services for channel management and account mappings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.core import Account, AccountChannelMap, Channel
from ..utils.settings import get_settings


class ChannelServiceError(Exception):
    """Base error for channel related operations."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class ChannelNotFound(ChannelServiceError):
    """Raised when a channel could not be located."""


class AccountNotFound(ChannelServiceError):
    """Raised when one or more accounts are missing."""


class ProjectMismatch(ChannelServiceError):
    """Raised when entities belong to different projects."""


class ChannelLimitExceeded(ChannelServiceError):
    """Raised when account to channel assignment exceeds the configured limit."""


@dataclass
class ChannelService:
    """Encapsulates channel specific business rules."""

    db: Session
    max_channels_per_account: int | None = None

    def __post_init__(self) -> None:  # pragma: no cover - simple settings lookup
        if self.max_channels_per_account is None:
            self.max_channels_per_account = get_settings().max_channels_per_account

    def assign_accounts(self, channel_id: int, account_ids: Sequence[int]) -> list[AccountChannelMap]:
        """Bind accounts to a channel while respecting account limits."""

        unique_account_ids = list(dict.fromkeys(account_ids))
        if not unique_account_ids:
            return []

        channel = self.db.get(Channel, channel_id)
        if channel is None:
            raise ChannelNotFound(f"Channel {channel_id} not found", status_code=404)

        accounts = (
            self.db.query(Account)
            .filter(Account.id.in_(unique_account_ids))
            .all()
        )
        found_ids = {account.id for account in accounts}
        missing = [account_id for account_id in unique_account_ids if account_id not in found_ids]
        if missing:
            raise AccountNotFound(
                f"Accounts not found: {', '.join(str(mid) for mid in missing)}",
                status_code=404,
            )

        for account in accounts:
            if account.project_id != channel.project_id:
                raise ProjectMismatch("Accounts and channel must belong to the same project")

        existing_links = (
            self.db.query(AccountChannelMap)
            .filter(
                AccountChannelMap.channel_id == channel_id,
                AccountChannelMap.account_id.in_(unique_account_ids),
            )
            .all()
        )
        already_assigned = {link.account_id for link in existing_links}

        ids_for_count = [account_id for account_id in unique_account_ids if account_id not in already_assigned]
        if ids_for_count:
            assignment_counts = dict(
                self.db.query(AccountChannelMap.account_id, func.count())
                .filter(AccountChannelMap.account_id.in_(ids_for_count))
                .group_by(AccountChannelMap.account_id)
                .all()
            )
        else:
            assignment_counts = {}

        limit = (
            self.max_channels_per_account
            if self.max_channels_per_account is not None
            else get_settings().max_channels_per_account
        )
        created: list[AccountChannelMap] = []

        for account in accounts:
            if account.id in already_assigned:
                continue
            current = assignment_counts.get(account.id, 0)
            if current >= limit:
                raise ChannelLimitExceeded(
                    f"Account {account.id} already assigned to {current} channels (limit {limit})"
                )
            mapping = AccountChannelMap(account_id=account.id, channel_id=channel_id)
            self.db.add(mapping)
            created.append(mapping)

        if created:
            self.db.commit()
            for mapping in created:
                self.db.refresh(mapping)
        else:
            self.db.flush()  # make sure session remains clean for callers expecting transaction state

        return created


__all__ = [
    "ChannelService",
    "ChannelServiceError",
    "ChannelNotFound",
    "AccountNotFound",
    "ProjectMismatch",
    "ChannelLimitExceeded",
]
