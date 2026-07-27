"""Session client (heartbeat / session-end) — HTTP clients only."""

from __future__ import annotations

import httpx

from baaboo_sso_auth.session_client import IdpSessionClient
from helpers import make_settings


def test_heartbeat_success() -> None:
    settings = make_settings()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/oauth/heartbeat"
        assert request.headers["Authorization"] == "Bearer jwt-x"
        return httpx.Response(204)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert IdpSessionClient(settings, http_client=client).heartbeat("jwt-x") is True


def test_heartbeat_401() -> None:
    settings = make_settings()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert IdpSessionClient(settings, http_client=client).heartbeat("jwt-x") is False


def test_end_session_best_effort() -> None:
    settings = make_settings()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/oauth/session/end"
        return httpx.Response(500)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    IdpSessionClient(settings, http_client=client).end_session("jwt-x")  # must not raise
