"""``/me`` response builder — fixed JSON shape for npm / SPA frontends."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from baaboo_sso_auth.claims import CurrentUser, SsoClaims

PermissionsResolver = Callable[[SsoClaims], Sequence[str]]
NameResolver = Callable[[SsoClaims], str]
RoleResolver = Callable[[SsoClaims], str]


@dataclass(frozen=True, slots=True)
class MePayload:
    name: str
    role: str
    permissions: list[str]

    def to_dict(self, *, wrap_data: bool = True) -> dict[str, Any]:
        body = {"name": self.name, "role": self.role, "permissions": self.permissions}
        if wrap_data:
            return {"data": body}
        return body


def default_permissions(claims: SsoClaims) -> list[str]:
    """Match Laravel ``MeController``: admin → ``["*"]``, else ``[]``."""
    if claims.project_role == "admin":
        return ["*"]
    return []


def default_name(claims: SsoClaims) -> str:
    return claims.email


def default_role(claims: SsoClaims) -> str:
    return claims.project_role


def build_me_response(
    user: CurrentUser | SsoClaims,
    *,
    permissions: Sequence[str] | PermissionsResolver | None = None,
    name: str | NameResolver | None = None,
    role: str | RoleResolver | None = None,
    wrap_data: bool = True,
) -> dict[str, Any]:
    """
    Build the fixed ``/me`` JSON shape.

    Permissions come from the **consumer app** (hook), not the IdP JWT.
    Pass a list or a callable; when omitted, admin gets ``["*"]``.
    """
    claims = user.claims if isinstance(user, CurrentUser) else user

    if callable(name):
        resolved_name = name(claims)
    elif name is not None:
        resolved_name = name
    else:
        resolved_name = default_name(claims)

    if callable(role):
        resolved_role = role(claims)
    elif role is not None:
        resolved_role = role
    else:
        resolved_role = default_role(claims)

    if callable(permissions):
        resolved_perms = list(permissions(claims))
    elif permissions is not None:
        resolved_perms = list(permissions)
    else:
        resolved_perms = default_permissions(claims)

    return MePayload(
        name=resolved_name,
        role=resolved_role,
        permissions=resolved_perms,
    ).to_dict(wrap_data=wrap_data)
