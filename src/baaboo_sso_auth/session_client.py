"""IdP heartbeat and session-end HTTP *clients* (call existing IdP endpoints)."""

from __future__ import annotations

import httpx

from baaboo_sso_auth.config import SsoSettings
from baaboo_sso_auth.constants import OAUTH_HEARTBEAT_PATH, OAUTH_SESSION_END_PATH


class IdpSessionClient:
    """
    Server-to-server session lifecycle against the existing IdP.

    - Heartbeat client: ``POST {SSO_BASE_URL}/oauth/heartbeat`` with Bearer JWT
    - Session-end client: ``POST {SSO_BASE_URL}/oauth/session/end`` with Bearer JWT
    """

    def __init__(
        self,
        settings: SsoSettings,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings
        self._http_client = http_client

    @property
    def heartbeat_url(self) -> str:
        return f"{self._settings.base_url}{OAUTH_HEARTBEAT_PATH}"

    @property
    def session_end_url(self) -> str:
        return f"{self._settings.base_url}{OAUTH_SESSION_END_PATH}"

    def heartbeat(self, access_token: str) -> bool:
        """
        Touch the IdP activity session.

        Returns True on 2xx. Returns False on 401 or transport failure
        (caller should treat as logged out).
        """
        token = access_token.strip()
        if not token:
            return False
        return self._post_bearer(self.heartbeat_url, token, best_effort=False)

    def end_session(self, access_token: str) -> None:
        """Best-effort IdP session end — local cookie clear must still succeed."""
        token = access_token.strip()
        if not token:
            return
        self._post_bearer(self.session_end_url, token, best_effort=True)

    def _post_bearer(self, url: str, token: str, *, best_effort: bool) -> bool:
        client = self._http_client or httpx.Client(
            timeout=10.0, verify=self._settings.httpx_verify
        )
        owns_client = self._http_client is None
        try:
            response = client.post(
                url,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {token}",
                },
            )
            if best_effort:
                return True
            return 200 <= response.status_code < 300
        except httpx.HTTPError:
            if best_effort:
                return True
            return False
        finally:
            if owns_client:
                client.close()
