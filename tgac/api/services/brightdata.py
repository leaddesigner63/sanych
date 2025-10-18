"""Lightweight client for interacting with Bright Data proxy endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class BrightDataError(Exception):
    """Base error for Bright Data related failures."""


@dataclass(frozen=True, slots=True)
class BrightDataProxy:
    """Represents a proxy allocated from Bright Data."""

    host: str
    port: int
    username: str
    password: str
    zone: str
    country: str | None = None
    session_id: str | None = None
    protocol: str = "http"


class BrightDataClient:
    """Minimal synchronous client for reserving Bright Data proxies."""

    def __init__(
        self,
        username: str,
        password: str,
        *,
        base_url: str = "https://api.brightdata.com",
        http_client: httpx.Client | None = None,
    ) -> None:
        self.username = username
        self.password = password
        self.base_url = base_url.rstrip("/")
        self._http = http_client or httpx.Client(timeout=10.0)
        self._owns_client = http_client is None

    def request_proxy(
        self,
        *,
        zone: str = "residential",
        country: str | None = None,
        session_id: str | None = None,
    ) -> BrightDataProxy:
        """Request a proxy from Bright Data's API."""

        params: dict[str, Any] = {"zone": zone}
        if country:
            params["country"] = country
        if session_id:
            params["session_id"] = session_id

        url = f"{self.base_url}/proxy"
        try:
            response = self._http.get(
                url,
                params=params,
                auth=(self.username, self.password),
                timeout=10.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network failure path
            raise BrightDataError(f"Failed to request proxy: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise BrightDataError("Invalid JSON response from Bright Data") from exc

        host = payload.get("host")
        port = payload.get("port")
        username = payload.get("username") or payload.get("user")
        password = payload.get("password")
        protocol = (payload.get("protocol") or "http").lower()

        if not host or not isinstance(host, str):
            raise BrightDataError("Bright Data response missing host")
        if not isinstance(port, int):
            raise BrightDataError("Bright Data response missing port")
        if not username or not isinstance(username, str):
            raise BrightDataError("Bright Data response missing username")
        if not password or not isinstance(password, str):
            raise BrightDataError("Bright Data response missing password")

        return BrightDataProxy(
            host=host,
            port=port,
            username=username,
            password=password,
            zone=str(payload.get("zone") or zone),
            country=payload.get("country") or country,
            session_id=payload.get("session_id") or session_id,
            protocol=protocol,
        )

    def close(self) -> None:  # pragma: no cover - passthrough to httpx
        if self._owns_client:
            self._http.close()


__all__ = ["BrightDataClient", "BrightDataError", "BrightDataProxy"]
