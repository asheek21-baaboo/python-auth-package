"""Pytest fixtures."""

from __future__ import annotations

import pytest

from helpers import ensure_keys


@pytest.fixture(autouse=True)
def _keys_and_settings_cache() -> None:
    from baaboo_sso_auth.config import configure, get_settings

    ensure_keys()
    configure(None)
    get_settings.cache_clear()
    yield
    configure(None)
    get_settings.cache_clear()
