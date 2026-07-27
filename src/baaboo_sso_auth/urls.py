"""Authorize / redirect URI helpers (browser → existing IdP authorize)."""

from __future__ import annotations

from urllib.parse import urlencode

from baaboo_sso_auth.config import SsoSettings
from baaboo_sso_auth.constants import CALLBACK_PATH, OAUTH_AUTHORIZE_PATH


def redirect_uri(settings: SsoSettings) -> str:
    """IdP-registered redirect URI: ``{APP_URL}/oauth/callback``."""
    return f"{settings.app_url.rstrip('/')}{CALLBACK_PATH}"


def build_authorize_url(
    settings: SsoSettings,
    *,
    prompt: str | None = None,
    extra_params: dict[str, str] | None = None,
) -> str:
    """
    Build the IdP authorize URL for browser login redirects.

    Query mirrors the Laravel package / portal:
    ``project_id``, ``client_id``, ``redirect_uri``, ``response_type=code``.
    """
    params: dict[str, str] = {
        "project_id": settings.project_id,
        "client_id": settings.resolved_client_id,
        "redirect_uri": redirect_uri(settings),
        "response_type": "code",
    }
    if prompt:
        params["prompt"] = prompt
    if extra_params:
        params.update(extra_params)
    return f"{settings.base_url}{OAUTH_AUTHORIZE_PATH}?{urlencode(params)}"
