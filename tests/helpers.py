"""Shared test helpers — generate RS256 JWTs for verifier tests only (not an IdP)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from baaboo_sso_auth.config import SsoSettings, get_settings

FIXTURES = Path(__file__).parent / "fixtures"
PRIVATE_PEM = FIXTURES / "test_private.pem"
PUBLIC_PEM = FIXTURES / "test_public.pem"
KID = "baaboo-sso-1"


def ensure_keys() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    if PRIVATE_PEM.exists() and PUBLIC_PEM.exists():
        return
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    PRIVATE_PEM.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    PUBLIC_PEM.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )


def private_key():
    ensure_keys()
    return serialization.load_pem_private_key(
        PRIVATE_PEM.read_bytes(),
        password=None,
        backend=default_backend(),
    )


def public_key():
    ensure_keys()
    return serialization.load_pem_public_key(PUBLIC_PEM.read_bytes(), backend=default_backend())


def jwks_dict() -> dict[str, Any]:
    from jwt.algorithms import RSAAlgorithm

    pub = public_key()
    jwk = RSAAlgorithm.to_jwk(pub, as_dict=True)
    jwk["kid"] = KID
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    return {"keys": [jwk]}


def make_settings(**overrides: Any) -> SsoSettings:
    get_settings.cache_clear()
    kwargs = {
        "sso_base_url": "https://sso.test",
        "project_id": "demo-app",
        "client_id": "demo-client",
        "client_secret": "secret",
        "app_url": "https://app.test",
        "environment": "local",
        "cookie_secure": False,
        "heartbeat_interval_seconds": 0,
        "redirect_after_login": "/",
        "redirect_to_idp_logout": True,
    }
    kwargs.update(overrides)
    return SsoSettings(_env_file=None, **kwargs)  # type: ignore[call-arg]


def mint_token(**claim_overrides: Any) -> str:
    """Sign a test JWT with the fixture private key (test helper only)."""
    now = int(time.time())
    claims = {
        "sub": "user-1",
        "email": "user@example.com",
        "iss": "https://sso.test",
        "aud": "demo-app",
        "project_id": "demo-app",
        "project_role": "manager",
        "global_role": "staff",
        "createUser": False,
        "jti": "jti-1",
        "iat": now,
        "exp": now + 3600,
    }
    claims.update(claim_overrides)
    return jwt.encode(claims, private_key(), algorithm="RS256", headers={"kid": KID})
