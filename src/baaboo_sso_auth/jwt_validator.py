"""JWKS fetch + RS256 JWT verification (client of IdP JWKS — does not issue tokens)."""

from __future__ import annotations

import ssl
import threading
import time
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient

from baaboo_sso_auth.claims import SsoClaims
from baaboo_sso_auth.config import SsoSettings
from baaboo_sso_auth.constants import JWT_LEEWAY_SECONDS
from baaboo_sso_auth.exceptions import InvalidTokenError


class JwtValidator:
    """
    Verify IdP-issued RS256 JWTs via the existing IdP JWKS endpoint.

    This is a consumer verifier only — it never signs JWTs or holds private keys.
    """

    def __init__(
        self,
        settings: SsoSettings,
        *,
        http_client: httpx.Client | None = None,
        jwks: dict[str, Any] | None = None,
    ) -> None:
        self._settings = settings
        self._http_client = http_client
        self._static_jwks = jwks
        self._cached_at: float = 0.0
        self._lock = threading.Lock()
        self._jwk_client: PyJWKClient | None = None

    @property
    def jwks_url(self) -> str:
        return f"{self._settings.base_url}{self._settings.jwks_path}"

    def forget_cached_key(self) -> None:
        with self._lock:
            self._cached_at = 0.0
            self._jwk_client = None

    def validate(self, token: str, *, require_claims: bool = True) -> SsoClaims:
        try:
            signing_key = self._signing_key(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._settings.project_id,
                issuer=self._settings.issuer,
                leeway=JWT_LEEWAY_SECONDS,
                options={
                    "require": ["exp", "iat", "iss", "aud", "sub"],
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )
        except jwt.ExpiredSignatureError as exc:
            raise InvalidTokenError.expired() from exc
        except jwt.InvalidSignatureError as exc:
            raise InvalidTokenError.invalid_signature() from exc
        except jwt.InvalidAudienceError as exc:
            raise InvalidTokenError.claim_mismatch("aud") from exc
        except jwt.InvalidIssuerError as exc:
            raise InvalidTokenError.claim_mismatch("iss") from exc
        except jwt.PyJWTError as exc:
            raise InvalidTokenError.malformed(str(exc)) from exc
        except InvalidTokenError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise InvalidTokenError.unresolvable_key() from exc

        if not isinstance(payload, dict):
            raise InvalidTokenError.malformed()

        project_id = payload.get("project_id")
        if project_id is not None and project_id != self._settings.project_id:
            raise InvalidTokenError.claim_mismatch("project_id")

        jti = payload.get("jti")
        if require_claims and (not isinstance(jti, str) or not jti):
            raise InvalidTokenError.missing_claim("jti")

        try:
            return SsoClaims.from_dict(payload)
        except ValueError as exc:
            raise InvalidTokenError.malformed(str(exc)) from exc

    def _signing_key(self, token: str) -> Any:
        if self._static_jwks is not None:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            jwk_set = jwt.PyJWKSet.from_dict(self._static_jwks)
            for key in jwk_set.keys:
                if kid is None or key.key_id == kid:
                    return key
            raise InvalidTokenError.unresolvable_key()

        client = self._ensure_jwk_client()
        return client.get_signing_key_from_jwt(token)

    def _ensure_jwk_client(self) -> PyJWKClient:
        with self._lock:
            now = time.monotonic()
            ttl = self._settings.jwks_cache_ttl
            if self._jwk_client is not None and (now - self._cached_at) < ttl:
                return self._jwk_client

            self._fetch_jwks()
            self._jwk_client = PyJWKClient(
                self.jwks_url,
                cache_keys=True,
                lifespan=ttl,
                headers={"Accept": "application/json"},
                ssl_context=self._jwk_ssl_context(),
            )
            self._cached_at = now
            return self._jwk_client

    def _jwk_ssl_context(self) -> ssl.SSLContext | None:
        """
        PyJWKClient fetches JWKS via ``urllib`` internally, independent of
        ``_http_client`` — it needs its own SSL context to honor the same
        verification settings (custom CA bundle or disabled verification).
        """
        verify = self._settings.httpx_verify
        if verify is True:
            return None
        if verify is False:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            return context
        return ssl.create_default_context(cafile=verify)

    def _fetch_jwks(self) -> dict[str, Any]:
        client = self._http_client or httpx.Client(
            timeout=5.0, verify=self._settings.httpx_verify
        )
        owns_client = self._http_client is None
        try:
            response = client.get(self.jwks_url, headers={"Accept": "application/json"})
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or "keys" not in data:
                raise InvalidTokenError.unresolvable_key()
            return data
        except InvalidTokenError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise InvalidTokenError.unresolvable_key() from exc
        finally:
            if owns_client:
                client.close()
