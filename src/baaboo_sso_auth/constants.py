"""Platform constants aligned with the Laravel Composer auth package."""

from __future__ import annotations

# IdP paths (relative to SSO_BASE_URL)
JWKS_PATH = "/.well-known/jwks.json"
JWKS_PATH_ALT = "/jwks"
OAUTH_AUTHORIZE_PATH = "/oauth/authorize"
OAUTH_TOKEN_PATH = "/oauth/token"
OAUTH_HEARTBEAT_PATH = "/oauth/heartbeat"
OAUTH_SESSION_END_PATH = "/oauth/session/end"

# App-owned cookie — mirrors CompanyAuth::TOKEN_COOKIE_NAME
TOKEN_COOKIE_NAME = "token"
TOKEN_COOKIE_MAX_AGE_SECONDS = 36_000  # 10 hours
ACCESS_TOKEN_TTL_SECONDS = 36_000

# Cache JWKS for one hour (CompanyAuth::JWKS_CACHE_TTL)
JWKS_CACHE_TTL_SECONDS = 3600

# Clock skew when validating exp / iat
JWT_LEEWAY_SECONDS = 60

# App routes registered by framework adapters
CALLBACK_PATH = "/oauth/callback"
LOGIN_PATH = "/login"
LOGOUT_PATH = "/logout"
ME_PATH = "/me"
TOKEN_EXPIRED_PATH = "/oauth/token-expired"
ERROR_PATH = "/oauth/error"

DEFAULT_PRODUCTION_IDP_URL = "https://sso.baaboo.com"
