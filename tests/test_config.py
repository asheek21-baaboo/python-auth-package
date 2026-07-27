"""Config / settings tests."""

from __future__ import annotations

from baaboo_sso_auth.config import SsoSettings, get_settings


def test_client_id_defaults_to_project_id() -> None:
    get_settings.cache_clear()
    s = SsoSettings(  # type: ignore[call-arg]
        sso_base_url="https://sso.test",
        project_id="my-app",
        client_id=None,
        client_secret="sec",
        app_url="https://app.test",
        environment="local",
    )
    assert s.resolved_client_id == "my-app"


def test_idp_url_alias() -> None:
    get_settings.cache_clear()
    s = SsoSettings(  # type: ignore[call-arg]
        sso_base_url=None,
        idp_url="https://baaboo-sso.test",
        project_id="my-app",
        client_secret="sec",
        app_url="https://app.test",
        environment="local",
    )
    assert s.base_url == "https://baaboo-sso.test"


def test_local_fallback_default_https() -> None:
    get_settings.cache_clear()
    s = SsoSettings(  # type: ignore[call-arg]
        sso_base_url=None,
        idp_url=None,
        project_id="my-app",
        client_secret="sec",
        app_url="https://app.test",
        environment="local",
    )
    assert s.base_url == "https://baaboo-sso.test"


def test_local_fallback_uses_sso_local_base_url() -> None:
    get_settings.cache_clear()
    s = SsoSettings(  # type: ignore[call-arg]
        sso_base_url=None,
        idp_url=None,
        sso_local_base_url="https://custom-sso.test",
        project_id="my-app",
        client_secret="sec",
        app_url="https://app.test",
        environment="local",
    )
    assert s.base_url == "https://custom-sso.test"
