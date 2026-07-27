"""Optional local-user provisioning hook when JWT ``createUser`` is true."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from baaboo_sso_auth.claims import SsoClaims
from baaboo_sso_auth.exceptions import UserNotProvisionedError


class UserStore(Protocol):
    """Minimal store interface for find / upsert by email."""

    def find_by_email(self, email: str) -> Any | None: ...

    def upsert(self, *, email: str, sub: str, claims: SsoClaims) -> Any: ...


FindByEmail = Callable[[str], Any | None]
UpsertUser = Callable[[SsoClaims], Any]


def sync_user(
    claims: SsoClaims,
    *,
    find_by_email: FindByEmail | None = None,
    upsert: UpsertUser | None = None,
    store: UserStore | None = None,
) -> Any | None:
    """
    Mirror Laravel ``UserSynchronizer``:

    - ``createUser`` true → upsert local user
    - ``createUser`` false → require existing local user or raise

    If no store/hooks are configured, returns ``None`` (JWT-only consumer apps).
    """
    has_hooks = store is not None or find_by_email is not None or upsert is not None
    if not has_hooks:
        return None

    email = claims.email

    def _find(e: str) -> Any | None:
        if store is not None:
            return store.find_by_email(e)
        if find_by_email is not None:
            return find_by_email(e)
        return None

    def _upsert(c: SsoClaims) -> Any:
        if store is not None:
            return store.upsert(email=c.email, sub=c.sub, claims=c)
        if upsert is not None:
            return upsert(c)
        raise RuntimeError("No upsert handler configured for createUser provisioning.")

    if claims.create_user:
        return _upsert(claims)

    existing = _find(email)
    if existing is None:
        raise UserNotProvisionedError(email)
    return existing
