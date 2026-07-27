"""SSO settings loaded from environment (SSO_* / IDP_URL aliases)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from baaboo_sso_auth.constants import (
    DEFAULT_PRODUCTION_IDP_URL,
    JWKS_CACHE_TTL_SECONDS,
    JWKS_PATH,
)


class SsoSettings(BaseSettings):
    """
    Consumer-app SSO configuration.

    Required for token exchange: ``SSO_PROJECT_ID``, ``SSO_CLIENT_SECRET``,
    and a base URL (``SSO_BASE_URL`` or Laravel alias ``IDP_URL``).

    **Never** expose ``SSO_CLIENT_SECRET`` to browsers or frontend bundles.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    sso_base_url: str | None = Field(default=None, validation_alias="SSO_BASE_URL")
    idp_url: str | None = Field(default=None, validation_alias="IDP_URL")
    sso_local_base_url: str | None = Field(default=None, validation_alias="SSO_LOCAL_BASE_URL")
    project_id: str = Field(validation_alias="SSO_PROJECT_ID")
    client_id: str | None = Field(default=None, validation_alias="SSO_CLIENT_ID")
    client_secret: str = Field(validation_alias="SSO_CLIENT_SECRET")
    app_url: str = Field(validation_alias="APP_URL")
    redirect_after_login: str = Field(default="/", validation_alias="SSO_REDIRECT_AFTER_LOGIN")
    redirect_to_idp_logout: bool = Field(default=True, validation_alias="SSO_REDIRECT_TO_IDP_LOGOUT")
    cookie_secure: bool | None = Field(default=None, validation_alias="SSO_COOKIE_SECURE")
    verify_ssl: bool | None = Field(default=None, validation_alias="SSO_VERIFY_SSL")
    jwks_cache_ttl: int = Field(default=JWKS_CACHE_TTL_SECONDS, validation_alias="SSO_JWKS_CACHE_TTL")
    jwks_path: str = Field(default=JWKS_PATH, validation_alias="SSO_JWKS_PATH")
    heartbeat_interval_seconds: int = Field(
        default=60,
        validation_alias="SSO_HEARTBEAT_INTERVAL_SECONDS",
    )
    environment: str = Field(default="production", validation_alias="APP_ENV")

    @field_validator("sso_base_url", "idp_url", "sso_local_base_url", "app_url", mode="before")
    @classmethod
    def _strip_trailing_slash(cls, value: object) -> object:
        if isinstance(value, str):
            return value.rstrip("/")
        return value

    @model_validator(mode="after")
    def _resolve_defaults(self) -> SsoSettings:
        if not self.client_id:
            object.__setattr__(self, "client_id", self.project_id)
        if not self.redirect_after_login:
            object.__setattr__(self, "redirect_after_login", "/")
        return self

    @property
    def base_url(self) -> str:
        """Resolved IdP root (no trailing slash)."""
        for candidate in (self.sso_base_url, self.idp_url):
            if candidate:
                return candidate.rstrip("/")
        if self.environment.lower() == "local":
            if self.sso_local_base_url:
                return self.sso_local_base_url.rstrip("/")
            return "https://baaboo-sso.test"
        return DEFAULT_PRODUCTION_IDP_URL

    @property
    def issuer(self) -> str:
        """Expected JWT ``iss`` — same as IdP base URL."""
        return self.base_url

    @property
    def resolved_client_id(self) -> str:
        assert self.client_id is not None
        return self.client_id

    def cookie_should_be_secure(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.environment.lower() != "local"

    @property
    def should_verify_ssl(self) -> bool:
        """
        Whether outgoing HTTPS calls to the IdP should verify the TLS certificate.

        Defaults to ``False`` for ``APP_ENV=local`` (local dev stacks such as
        EnvKit/Laragon/mkcert provision self-signed certs for ``*.test`` hosts
        like ``https://baaboo-sso.test``), and ``True`` everywhere else.
        Override explicitly with ``SSO_VERIFY_SSL=true|false``.
        """
        if self.verify_ssl is not None:
            return self.verify_ssl
        return self.environment.lower() != "local"


_settings_override: SsoSettings | None = None


def configure(settings: SsoSettings | None) -> None:
    """
    Optionally pin settings for the process (useful in tests / FastAPI startup).

    Pass ``None`` to clear the override and fall back to env-backed ``get_settings()``.
    """
    global _settings_override
    _settings_override = settings
    get_settings.cache_clear()


@lru_cache
def get_settings() -> SsoSettings:
    """Cached settings singleton (clear with ``get_settings.cache_clear()`` in tests)."""
    if _settings_override is not None:
        return _settings_override
    return SsoSettings()  # type: ignore[call-arg]
