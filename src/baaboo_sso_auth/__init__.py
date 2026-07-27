"""baaboo SSO auth for Python apps — consumer client of the existing IdP."""

from baaboo_sso_auth.claims import CurrentUser, SsoClaims
from baaboo_sso_auth.config import SsoSettings, configure, get_settings
from baaboo_sso_auth.constants import (
    ACCESS_TOKEN_TTL_SECONDS,
    JWKS_PATH,
    OAUTH_AUTHORIZE_PATH,
    OAUTH_HEARTBEAT_PATH,
    OAUTH_SESSION_END_PATH,
    OAUTH_TOKEN_PATH,
    TOKEN_COOKIE_NAME,
)
from baaboo_sso_auth.exceptions import (
    CodeExchangeError,
    InvalidTokenError,
    SsoAuthError,
    UserNotProvisionedError,
)
from baaboo_sso_auth.jwt_validator import JwtValidator
from baaboo_sso_auth.me import MePayload, build_me_response
from baaboo_sso_auth.provisioning import sync_user
from baaboo_sso_auth.session_client import IdpSessionClient
from baaboo_sso_auth.token_exchanger import TokenExchanger
from baaboo_sso_auth.urls import build_authorize_url, redirect_uri

__all__ = [
    "ACCESS_TOKEN_TTL_SECONDS",
    "CodeExchangeError",
    "CurrentUser",
    "IdpSessionClient",
    "InvalidTokenError",
    "JWKS_PATH",
    "JwtValidator",
    "MePayload",
    "OAUTH_AUTHORIZE_PATH",
    "OAUTH_HEARTBEAT_PATH",
    "OAUTH_SESSION_END_PATH",
    "OAUTH_TOKEN_PATH",
    "SsoAuthError",
    "SsoClaims",
    "SsoSettings",
    "TOKEN_COOKIE_NAME",
    "TokenExchanger",
    "UserNotProvisionedError",
    "build_authorize_url",
    "build_me_response",
    "configure",
    "get_settings",
    "redirect_uri",
    "sync_user",
]

__version__ = "0.1.0"
