from __future__ import annotations

import pytest

from tgac.api.services.brightdata import BrightDataClient, BrightDataError


class DummyResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class DummyHttpClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def get(self, url: str, *, params: dict, auth: tuple[str, str], timeout: float) -> DummyResponse:
        self.calls.append({"url": url, "params": params, "auth": auth, "timeout": timeout})
        return DummyResponse(self.payload)


def test_brightdata_client_parses_successful_response() -> None:
    payload = {
        "host": "brd.superproxy.io",
        "port": 22225,
        "username": "user",
        "password": "pass",
        "protocol": "socks5",
        "zone": "residential",
        "country": "us",
        "session_id": "abc",
    }
    client = DummyHttpClient(payload)
    bright = BrightDataClient("cust", "secret", http_client=client)

    proxy = bright.request_proxy(zone="residential", country="us", session_id="abc")

    assert proxy.host == "brd.superproxy.io"
    assert proxy.port == 22225
    assert proxy.username == "user"
    assert proxy.password == "pass"
    assert proxy.zone == "residential"
    assert proxy.country == "us"
    assert client.calls[0]["params"]["zone"] == "residential"
    assert client.calls[0]["params"]["country"] == "us"
    assert client.calls[0]["auth"] == ("cust", "secret")


def test_brightdata_client_raises_on_invalid_payload() -> None:
    payload = {"host": "", "port": "not-int", "username": "", "password": ""}
    client = DummyHttpClient(payload)
    bright = BrightDataClient("cust", "secret", http_client=client)

    with pytest.raises(BrightDataError):
        bright.request_proxy()
