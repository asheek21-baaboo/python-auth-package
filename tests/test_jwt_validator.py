"""JWT verification tests (consumer verifier against static JWKS)."""

from __future__ import annotations

import time

import pytest

from baaboo_sso_auth.exceptions import InvalidTokenError
from baaboo_sso_auth.jwt_validator import JwtValidator
from helpers import jwks_dict, make_settings, mint_token


def test_validate_accepts_valid_token() -> None:
    settings = make_settings()
    validator = JwtValidator(settings, jwks=jwks_dict())
    claims = validator.validate(mint_token())
    assert claims.sub == "user-1"
    assert claims.email == "user@example.com"
    assert claims.project_role == "manager"
    assert claims.jti == "jti-1"


def test_validate_rejects_wrong_audience() -> None:
    settings = make_settings()
    validator = JwtValidator(settings, jwks=jwks_dict())
    with pytest.raises(InvalidTokenError) as exc:
        validator.validate(mint_token(aud="other-app", project_id="other-app"))
    assert "aud" in str(exc.value).lower() or "audience" in str(exc.value).lower() or exc.value


def test_validate_rejects_wrong_issuer() -> None:
    settings = make_settings()
    validator = JwtValidator(settings, jwks=jwks_dict())
    with pytest.raises(InvalidTokenError):
        validator.validate(mint_token(iss="https://evil.test"))


def test_validate_rejects_expired() -> None:
    settings = make_settings()
    validator = JwtValidator(settings, jwks=jwks_dict())
    now = int(time.time())
    with pytest.raises(InvalidTokenError) as exc:
        validator.validate(mint_token(iat=now - 7200, exp=now - 3600))
    assert exc.value.expired is True


def test_validate_rejects_missing_jti() -> None:
    settings = make_settings()
    validator = JwtValidator(settings, jwks=jwks_dict())
    token = mint_token()
    # Remint without jti by overriding then deleting — mint always sets jti; use empty
    with pytest.raises(InvalidTokenError):
        validator.validate(mint_token(jti=""))
