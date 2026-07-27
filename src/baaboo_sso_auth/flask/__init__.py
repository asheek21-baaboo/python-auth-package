"""Flask integration — Blueprint + decorator (consumer client only)."""

from __future__ import annotations

import re
from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import (
    Blueprint,
    g,
    jsonify,
    redirect,
    request,
    make_response,
)

from baaboo_sso_auth.claims import CurrentUser
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


def _apply_cookie(response: Any, params: dict) -> Any:
    key = params.pop("key")
    value = params.pop("value")
    max_age = params.pop("max_age", None)
    expires = params.pop("expires", None)
    response.set_cookie(
        key,
        value,
        max_age=max_age,
        expires=expires,
        path=params.get("path", "/"),
        domain=params.get("domain"),
        secure=params.get("secure", True),
        httponly=params.get("httponly", True),
        samesite=params.get("samesite", "Lax"),
    )
    return response


def require_auth(view: Callable[..., Any]) -> Callable[..., Any]:
    """Flask decorator — mirrors ``company.auth``."""

    @wraps(view)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        settings = get_settings()
        token = extract_token(
            authorization=request.headers.get("Authorization"),
            cookies=request.cookies,  # type: ignore[arg-type]
        )
        if token is None:
            if request.accept_mimetypes.best == "application/json":
                return jsonify({"message": "Unauthenticated."}), 401
            return redirect(f"{ERROR_PATH}?stub=unauthenticated")

        try:
            claims = JwtValidator(settings).validate(token)
        except InvalidTokenError as exc:
            if exc.expired and request.accept_mimetypes.best != "application/json":
                resp = make_response(redirect(TOKEN_EXPIRED_PATH))
                return _apply_cookie(resp, cookie_params(settings, clear=True))
            return jsonify({"message": str(exc)}), 401

        g.sso_token = token
        g.sso_claims = claims
        g.current_user = CurrentUser(claims)
        return view(*args, **kwargs)

    return wrapper


def create_sso_blueprint(
    *,
    settings: SsoSettings | None = None,
    permissions_resolver: PermissionsResolver | None = None,
    find_by_email: FindByEmail | None = None,
    upsert_user: UpsertUser | None = None,
    include_me: bool = True,
    wrap_me_data: bool = True,
    name: str = "baaboo_sso",
) -> Blueprint:
    """Flask Blueprint with login / callback / logout / error / optional /me."""
    bp = Blueprint(name, __name__)
    if settings is not None:
        configure(settings)

    def _cfg() -> SsoSettings:
        return get_settings()

    @bp.get(LOGIN_PATH)
    def login() -> Any:
        return redirect(build_authorize_url(_cfg()))

    @bp.get(CALLBACK_PATH)
    def oauth_callback() -> Any:
        cfg = _cfg()
        code = request.args.get("code")
        if not code or not _CODE_RE.match(code):
            return "Missing or invalid authorization code.", 400

        try:
            jwt_token = TokenExchanger(cfg).exchange(code)
            claims = JwtValidator(cfg).validate(jwt_token)
        except (CodeExchangeError, InvalidTokenError) as exc:
            return str(exc), 403

        try:
            sync_user(claims, find_by_email=find_by_email, upsert=upsert_user)
        except UserNotProvisionedError:
            return redirect(f"{ERROR_PATH}?stub=user_not_provisioned")
        except RuntimeError:
            pass

        resp = make_response(redirect(cfg.redirect_after_login or "/"))
        return _apply_cookie(resp, cookie_params(cfg, jwt=jwt_token))

    @bp.post(LOGOUT_PATH)
    def logout() -> Any:
        cfg = _cfg()
        token = extract_token(
            authorization=request.headers.get("Authorization"),
            cookies=request.cookies,  # type: ignore[arg-type]
        )
        if cfg.redirect_to_idp_logout and token:
            IdpSessionClient(cfg).end_session(token)
        resp = make_response(redirect(f"{ERROR_PATH}?stub=logged_out"))
        return _apply_cookie(resp, cookie_params(cfg, clear=True))

    @bp.get(TOKEN_EXPIRED_PATH)
    def token_expired() -> str:
        return (
            "<h1>Token expired</h1>"
            f'<p><a href="{LOGIN_PATH}">Sign in again</a></p>'
        )

    @bp.get(ERROR_PATH)
    def oauth_error() -> str:
        info = resolve_error_stub(request.args.get("stub"))
        return f"<h1>{info['message']}</h1><p>{info['description']}</p>"

    if include_me:

        @bp.get(ME_PATH)
        @require_auth
        def me() -> Any:
            user: CurrentUser = g.current_user
            return jsonify(
                build_me_response(
                    user,
                    permissions=permissions_resolver,
                    wrap_data=wrap_me_data,
                )
            )

    return bp


__all__ = ["create_sso_blueprint", "require_auth"]
