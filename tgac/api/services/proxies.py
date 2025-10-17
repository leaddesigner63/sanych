"""Business logic helpers for managing proxies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.core import Proxy, ProxyScheme
from ..utils.time import utcnow


class ProxyServiceError(Exception):
    """Base error for proxy service failures."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class ProxyNotFound(ProxyServiceError):
    """Raised when a proxy cannot be located."""


class ProxyNameExists(ProxyServiceError):
    """Raised when a proxy with the same name already exists in the project."""


@dataclass(frozen=True)
class ProxyCreateData:
    """Payload for creating a single proxy."""

    project_id: int
    name: str
    scheme: ProxyScheme
    host: str
    port: int
    username: str | None = None
    password: str | None = None


@dataclass(frozen=True)
class ProxyImportData:
    """Payload for bulk importing proxies."""

    name: str
    scheme: ProxyScheme
    host: str
    port: int
    username: str | None = None
    password: str | None = None


@dataclass
class ProxyImportSummary:
    """Information about the outcome of an import operation."""

    created: list[Proxy]
    skipped: list[str]


class ProxyService:
    """Encapsulates domain logic around proxies."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_proxy(self, payload: ProxyCreateData) -> Proxy:
        """Persist a new proxy ensuring uniqueness within the project."""

        existing = self.db.execute(
            select(Proxy.id).where(
                Proxy.project_id == payload.project_id, Proxy.name == payload.name
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ProxyNameExists(
                f"Proxy name '{payload.name}' already exists in project {payload.project_id}",
                status_code=409,
            )

        proxy = Proxy(
            project_id=payload.project_id,
            name=payload.name,
            scheme=payload.scheme,
            host=payload.host,
            port=payload.port,
            username=payload.username,
            password=payload.password,
        )
        self.db.add(proxy)
        self.db.commit()
        self.db.refresh(proxy)
        return proxy

    def import_proxies(
        self, project_id: int, entries: Sequence[ProxyImportData]
    ) -> ProxyImportSummary:
        """Bulk create proxies while avoiding duplicates by name."""

        if not entries:
            return ProxyImportSummary(created=[], skipped=[])

        names = [entry.name for entry in entries]
        existing = {
            name
            for (name,) in self.db.execute(
                select(Proxy.name).where(
                    Proxy.project_id == project_id, Proxy.name.in_(names)
                )
            ).all()
        }

        created: list[Proxy] = []
        skipped: list[str] = []
        seen: set[str] = set()

        for entry in entries:
            if entry.name in seen:
                skipped.append(entry.name)
                continue
            seen.add(entry.name)

            if entry.name in existing:
                skipped.append(entry.name)
                continue

            proxy = Proxy(
                project_id=project_id,
                name=entry.name,
                scheme=entry.scheme,
                host=entry.host,
                port=entry.port,
                username=entry.username,
                password=entry.password,
            )
            self.db.add(proxy)
            created.append(proxy)

        if created:
            self.db.commit()
            for proxy in created:
                self.db.refresh(proxy)
        else:
            self.db.flush()

        return ProxyImportSummary(created=created, skipped=skipped)

    def record_check(self, proxy_id: int, *, is_working: bool) -> Proxy:
        """Update health information about a proxy."""

        proxy = self.db.get(Proxy, proxy_id)
        if proxy is None:
            raise ProxyNotFound(f"Proxy {proxy_id} not found", status_code=404)

        proxy.is_working = is_working
        proxy.last_check_at = utcnow()
        self.db.commit()
        self.db.refresh(proxy)
        return proxy


__all__ = [
    "ProxyService",
    "ProxyServiceError",
    "ProxyNotFound",
    "ProxyNameExists",
    "ProxyCreateData",
    "ProxyImportData",
    "ProxyImportSummary",
]
