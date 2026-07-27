"""FastAPI consumer integration smoke tests."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from baaboo_sso_auth.config import configure
from baaboo_sso_auth.fastapi import create_sso_router
from baaboo_sso_auth.jwt_validator import JwtValidator
from helpers import jwks_dict, make_settings, mint_token


def test_login_redirects_to_idp() -> None:
    settings = make_settings()
    configure(settings)
    app = FastAPI()
    app.include_router(create_sso_router(settings=settings, include_me=False))
    client = TestClient(app, follow_redirects=False)
    resp = client.get("/login")
    assert resp.status_code == 302
    assert resp.headers["location"].startswith("https://sso.test/oauth/authorize?")


def test_me_with_bearer(monkeypatch) -> None:
    settings = make_settings()
    configure(settings)
    token = mint_token()
    jwks = jwks_dict()
    static_validator = JwtValidator(settings, jwks=jwks)

    monkeypatch.setattr(
        "baaboo_sso_auth.fastapi.create_validator",
        lambda settings=None: static_validator,
    )

    app = FastAPI()
    app.include_router(
        create_sso_router(
            settings=settings,
            permissions_resolver=lambda c: ["reports.view"],
        )
    )

    client = TestClient(app)
    resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["name"] == "user@example.com"
    assert body["data"]["role"] == "manager"
    assert body["data"]["permissions"] == ["reports.view"]
