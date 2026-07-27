"""Server-side authorization-code → JWT exchange against the existing IdP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from baaboo_sso_auth.config import SsoSettings
from baaboo_sso_auth.constants import OAUTH_TOKEN_PATH
from baaboo_sso_auth.exceptions import CodeExchangeError
from baaboo_sso_auth.urls import redirect_uri


@dataclass(frozen=True, slots=True)
class IdpTokenResponse:
    access_token: str
    expires_in: int
    token_type: str = "Bearer"

    @classmethod
    def from_dict(cls, body: dict[str, Any]) -> IdpTokenResponse:
        token = body.get("access_token")
        expires_in = body.get("expires_in")
        token_type = body.get("token_type", "Bearer")
        if not isinstance(token, str) or not token:
            raise CodeExchangeError.invalid_response()
        if not isinstance(expires_in, int):
            raise CodeExchangeError.invalid_response()
        if not isinstance(token_type, str):
            token_type = "Bearer"
        return cls(access_token=token, expires_in=expires_in, token_type=token_type)


class TokenExchanger:
    """POST ``{SSO_BASE_URL}/oauth/token`` with client credentials (server only)."""

    def __init__(
        self,
        settings: SsoSettings,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings
        self._http_client = http_client

    @property
    def token_url(self) -> str:
        return f"{self._settings.base_url}{OAUTH_TOKEN_PATH}"

    def exchange(self, code: str, *, callback_redirect_uri: str | None = None) -> str:
        """
        Exchange a one-time authorization code for an access JWT.

        Never call this from a browser — ``client_secret`` must stay server-side.
        """
        uri = callback_redirect_uri or redirect_uri(self._settings)
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": uri,
            "client_id": self._settings.resolved_client_id,
            "client_secret": self._settings.client_secret,
            "project_id": self._settings.project_id,
        }

        client = self._http_client or httpx.Client(
            timeout=10.0, verify=self._settings.should_verify_ssl
        )
        owns_client = self._http_client is None
        try:
            response = client.post(
                self.token_url,
                json=payload,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
        except httpx.HTTPError as exc:
            raise CodeExchangeError.transport_failed(str(exc)) from exc
        finally:
            if owns_client:
                client.close()

        if response.status_code >= 400:
            raise CodeExchangeError.idp_rejected(
                f"IdP token exchange failed with HTTP {response.status_code}."
            )

        try:
            body = response.json()
            if not isinstance(body, dict):
                raise CodeExchangeError.invalid_response()
            return IdpTokenResponse.from_dict(body).access_token
        except CodeExchangeError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise CodeExchangeError.invalid_response() from exc
