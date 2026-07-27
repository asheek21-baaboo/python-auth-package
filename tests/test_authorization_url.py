"""Authorize URL builder tests."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from baaboo_sso_auth.urls import build_authorize_url, redirect_uri
from helpers import make_settings


def test_redirect_uri() -> None:
    settings = make_settings()
    assert redirect_uri(settings) == "https://app.test/oauth/callback"


def test_build_authorize_url() -> None:
    settings = make_settings()
    url = build_authorize_url(settings)
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "sso.test"
    assert parsed.path == "/oauth/authorize"
    qs = parse_qs(parsed.query)
    assert qs["project_id"] == ["demo-app"]
    assert qs["client_id"] == ["demo-client"]
    assert qs["response_type"] == ["code"]
    assert qs["redirect_uri"] == ["https://app.test/oauth/callback"]


def test_build_authorize_url_with_prompt_login() -> None:
    settings = make_settings()
    url = build_authorize_url(settings, prompt="login")
    qs = parse_qs(urlparse(url).query)
    assert qs["prompt"] == ["login"]
