"""httpOnly JWT cookie helpers (name ``token``, SameSite=Lax, 10h)."""

from __future__ import annotations

from baaboo_sso_auth.config import SsoSettings
from baaboo_sso_auth.constants import TOKEN_COOKIE_MAX_AGE_SECONDS, TOKEN_COOKIE_NAME


def cookie_params(settings: SsoSettings, *, jwt: str | None = None, clear: bool = False) -> dict:
    """
    Keyword args suitable for Starlette ``Response.set_cookie`` / Flask ``set_cookie``.

    When ``clear`` is True, sets max_age=0 and empty value.
    """
    secure = settings.cookie_should_be_secure()
    if clear:
        return {
            "key": TOKEN_COOKIE_NAME,
            "value": "",
            "max_age": 0,
            "expires": 0,
            "path": "/",
            "domain": None,
            "secure": secure,
            "httponly": True,
            "samesite": "lax",
        }
    if jwt is None:
        raise ValueError("jwt is required unless clear=True")
    return {
        "key": TOKEN_COOKIE_NAME,
        "value": jwt,
        "max_age": TOKEN_COOKIE_MAX_AGE_SECONDS,
        "path": "/",
        "domain": None,
        "secure": secure,
        "httponly": True,
        "samesite": "lax",
    }


def extract_token(
    *,
    authorization: str | None = None,
    cookies: dict[str, str] | None = None,
) -> str | None:
    """Prefer ``Authorization: Bearer``, else httpOnly ``token`` cookie."""
    if authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
            return parts[1].strip()
    if cookies:
        cookie = cookies.get(TOKEN_COOKIE_NAME)
        if isinstance(cookie, str) and cookie:
            return cookie
    return None
