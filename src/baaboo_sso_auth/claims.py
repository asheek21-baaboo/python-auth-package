"""JWT claims and CurrentUser accessor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SsoClaims:
    """Parsed IdP access-token claims."""

    sub: str
    email: str
    project_role: str
    project_id: str
    aud: str
    iss: str
    jti: str
    global_role: str = "staff"
    create_user: bool = False
    iat: int | None = None
    exp: int | None = None
    raw: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SsoClaims:
        sub = payload.get("sub")
        email = payload.get("email")
        aud = payload.get("aud")
        iss = payload.get("iss")
        jti = payload.get("jti")
        project_role = payload.get("project_role")
        project_id = payload.get("project_id") or aud

        if not isinstance(sub, str) or not sub:
            raise ValueError("Missing claim: sub")
        if not isinstance(email, str) or not email:
            raise ValueError("Missing claim: email")
        if not isinstance(aud, str) or not aud:
            raise ValueError("Missing claim: aud")
        if not isinstance(iss, str) or not iss:
            raise ValueError("Missing claim: iss")
        if not isinstance(jti, str) or not jti:
            raise ValueError("Missing claim: jti")
        if not isinstance(project_role, str) or not project_role:
            raise ValueError("Missing claim: project_role")

        create_user = bool(payload.get("createUser", False))
        global_role = payload.get("global_role")
        if not isinstance(global_role, str) or not global_role:
            global_role = "staff"

        return cls(
            sub=sub,
            email=email,
            project_role=project_role,
            project_id=str(project_id),
            aud=aud,
            iss=iss,
            jti=jti,
            global_role=global_role,
            create_user=create_user,
            iat=payload.get("iat") if isinstance(payload.get("iat"), int) else None,
            exp=payload.get("exp") if isinstance(payload.get("exp"), int) else None,
            raw=dict(payload),
        )


class CurrentUser:
    """
    Request-scoped accessor for JWT claims (mirrors Laravel ``CurrentUser`` facade).

    Only use after auth middleware / dependency has run.
    """

    def __init__(self, claims: SsoClaims) -> None:
        self._claims = claims

    def id(self) -> str:
        return self._claims.sub

    def email(self) -> str:
        return self._claims.email

    def role(self) -> str:
        return self._claims.project_role

    def project_role(self) -> str:
        return self._claims.project_role

    def global_role(self) -> str:
        return self._claims.global_role

    def project_id(self) -> str:
        return self._claims.aud

    def jti(self) -> str:
        return self._claims.jti

    def create_user(self) -> bool:
        return self._claims.create_user

    def all(self) -> SsoClaims:
        return self._claims

    @property
    def claims(self) -> SsoClaims:
        return self._claims
