"""FastAPI integration — consumer routes & dependencies (not an IdP)."""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Sequence
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from baaboo_sso_auth.claims import CurrentUser, SsoClaims
from baaboo_sso_auth.config import SsoSettings, configure, get_settings
from baaboo_sso_auth.constants import (
    CALLBACK_PATH,
    ERROR_PATH,
    LOGIN_PATH,
    LOGOUT_PATH,
    ME_PATH,
    TOKEN_EXPIRED_PATH,
)
from baaboo_sso_auth.cookie import cookie_params, extract_token
from baaboo_sso_auth.errors import resolve_error_stub
from baaboo_sso_auth.exceptions import (
    CodeExchangeError,
    InvalidTokenError,
    UserNotProvisionedError,
)
from baaboo_sso_auth.jwt_validator import JwtValidator
from baaboo_sso_auth.me import PermissionsResolver, build_me_response
from baaboo_sso_auth.provisioning import FindByEmail, UpsertUser, sync_user
from baaboo_sso_auth.session_client import IdpSessionClient
from baaboo_sso_auth.token_exchanger import TokenExchanger
from baaboo_sso_auth.urls import build_authorize_url

_CODE_RE = re.compile(r"^[A-Za-z0-9\-._~/+]+=*$")

# Per-process heartbeat throttle: jti → last monotonic time
_heartbeat_last: dict[str, float] = {}


def _settings_dep() -> SsoSettings:
    return get_settings()


def create_validator(settings: SsoSettings | None = None) -> JwtValidator:
    return JwtValidator(settings or get_settings())


def require_user(
    request: Request,
    settings: Annotated[SsoSettings, Depends(_settings_dep)],
) -> CurrentUser:
    """FastAPI dependency — mirrors Laravel ``company.auth`` middleware."""
    token = extract_token(
        authorization=request.headers.get("authorization"),
        cookies=dict(request.cookies),
    )
    if token is None:
        accept = request.headers.get("accept", "")
        if "application/json" in accept or request.url.path.startswith("/api"):
            raise HTTPException(status_code=401, detail="Unauthenticated.")
        raise HTTPException(
            status_code=307,
            headers={"Location": f"{ERROR_PATH}?stub=unauthenticated"},
        )

    validator = create_validator(settings)
    try:
        claims = validator.validate(token)
    except InvalidTokenError as exc:
        headers = {"X-SSO-Token-Expired": "1"} if exc.expired else None
        raise HTTPException(status_code=401, detail=str(exc), headers=headers) from exc
    # Optional throttled heartbeat (client call to IdP)
    _maybe_heartbeat(settings, token, claims)

    request.state.sso_token = token
    request.state.sso_claims = claims
    request.state.current_user = CurrentUser(claims)
    return CurrentUser(claims)


def _maybe_heartbeat(settings: SsoSettings, token: str, claims: SsoClaims) -> None:
    interval = settings.heartbeat_interval_seconds
    if interval <= 0:
        return
    now = time.monotonic()
    last = _heartbeat_last.get(claims.jti, 0.0)
    if now - last < interval:
        return
    _heartbeat_last[claims.jti] = now
    client = IdpSessionClient(settings)
    if not client.heartbeat(token):
        # Closed / revoked session — surface as unauthenticated on next check
        raise HTTPException(status_code=401, detail="Session ended.")


def create_sso_router(
    *,
    settings: SsoSettings | None = None,
    permissions_resolver: PermissionsResolver | None = None,
    find_by_email: FindByEmail | None = None,
    upsert_user: UpsertUser | None = None,
    include_me: bool = True,
    wrap_me_data: bool = True,
) -> APIRouter:
    """
    Register consumer SSO routes (same surface as Laravel package):

    - ``GET /login`` → redirect to IdP authorize
    - ``GET /oauth/callback`` → code exchange + set cookie
    - ``POST /logout`` → IdP session/end + clear cookie
    - ``GET /oauth/token-expired``, ``GET /oauth/error``
    - optional ``GET /me`` (also wire with ``require_user`` yourself)
    """
    router = APIRouter(tags=["sso"])
    if settings is not None:
        configure(settings)

    def _cfg() -> SsoSettings:
        return get_settings()

    @router.get(LOGIN_PATH, name="login")
    def login() -> RedirectResponse:
        cfg = _cfg()
        return RedirectResponse(url=build_authorize_url(cfg), status_code=302)

    @router.get(CALLBACK_PATH, name="company-auth.callback")
    def oauth_callback(request: Request, code: str | None = None) -> Response:
        cfg = _cfg()
        if not code or not _CODE_RE.match(code):
            raise HTTPException(status_code=400, detail="Missing or invalid authorization code.")

        exchanger = TokenExchanger(cfg)
        validator = create_validator(cfg)
        try:
            jwt_token = exchanger.exchange(code)
            claims = validator.validate(jwt_token)
        except (CodeExchangeError, InvalidTokenError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

        try:
            sync_user(claims, find_by_email=find_by_email, upsert=upsert_user)
        except UserNotProvisionedError:
            return RedirectResponse(
                url=f"{ERROR_PATH}?stub=user_not_provisioned",
                status_code=303,
            )

        destination = cfg.redirect_after_login or "/"
        response = RedirectResponse(url=destination, status_code=303)
        response.set_cookie(**cookie_params(cfg, jwt=jwt_token))
        return response

    @router.post(LOGOUT_PATH, name="logout")
    def logout(request: Request) -> Response:
        cfg = _cfg()
        token = extract_token(
            authorization=request.headers.get("authorization"),
            cookies=dict(request.cookies),
        )
        if cfg.redirect_to_idp_logout and token:
            IdpSessionClient(cfg).end_session(token)

        response = RedirectResponse(url=f"{ERROR_PATH}?stub=logged_out", status_code=303)
        response.set_cookie(**cookie_params(cfg, clear=True))
        return response

    @router.get(TOKEN_EXPIRED_PATH, name="company-auth.token-expired")
    def token_expired() -> HTMLResponse:
        html = (
            "<!DOCTYPE html><html><body>"
            "<h1>Token expired</h1>"
            "<p>Your session has expired.</p>"
            f'<p><a href="{LOGIN_PATH}">Sign in again</a></p>'
            "</body></html>"
        )
        return HTMLResponse(html)

    @router.get(ERROR_PATH, name="company-auth.error")
    def oauth_error(stub: str | None = None) -> HTMLResponse:
        info = resolve_error_stub(stub)
        html = (
            "<!DOCTYPE html><html><body>"
            f"<h1>{info['message']}</h1>"
            f"<p>{info['description']}</p>"
            f'<p><a href="{LOGIN_PATH}">Sign in</a></p>'
            "</body></html>"
        )
        return HTMLResponse(html)

    if include_me:

        @router.get(ME_PATH, name="me")
        def me(user: Annotated[CurrentUser, Depends(require_user)]) -> JSONResponse:
            payload = build_me_response(
                user,
                permissions=permissions_resolver,
                wrap_data=wrap_me_data,
            )
            return JSONResponse(payload)

    return router


# Re-export type aliases for consumers
__all__ = [
    "create_sso_router",
    "require_user",
    "CurrentUser",
    "PermissionsResolver",
    "FindByEmail",
    "UpsertUser",
]
