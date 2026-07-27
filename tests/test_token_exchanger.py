"""Token exchange client tests (mocks IdP /oauth/token — does not implement IdP)."""

from __future__ import annotations

import httpx
import pytest

from baaboo_sso_auth.exceptions import CodeExchangeError
from baaboo_sso_auth.token_exchanger import TokenExchanger
from helpers import make_settings


def test_exchange_posts_expected_body() -> None:
    settings = make_settings()
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = httpx.Response(200).json if False else None
        import json

        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={"access_token": "jwt-here", "expires_in": 36000, "token_type": "Bearer"},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    exchanger = TokenExchanger(settings, http_client=client)
    token = exchanger.exchange("abc123")
    assert token == "jwt-here"
    assert captured["url"] == "https://sso.test/oauth/token"
    assert captured["body"]["grant_type"] == "authorization_code"
    assert captured["body"]["code"] == "abc123"
    assert captured["body"]["client_secret"] == "secret"
    assert captured["body"]["redirect_uri"] == "https://app.test/oauth/callback"
    assert captured["body"]["project_id"] == "demo-app"


def test_exchange_rejects_http_error() -> None:
    settings = make_settings()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"message": "Invalid code"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(CodeExchangeError):
        TokenExchanger(settings, http_client=client).exchange("bad")
