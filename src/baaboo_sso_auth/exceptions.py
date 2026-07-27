"""Typed SSO exceptions."""

from __future__ import annotations


class SsoAuthError(Exception):
    """Base error for baaboo SSO auth."""


class InvalidTokenError(SsoAuthError):
    """JWT failed verification or claim checks."""

    def __init__(self, message: str, *, expired: bool = False) -> None:
        super().__init__(message)
        self.expired = expired

    @classmethod
    def expired(cls) -> InvalidTokenError:
        return cls("Token has expired.", expired=True)

    @classmethod
    def invalid_signature(cls) -> InvalidTokenError:
        return cls("Invalid token signature.")

    @classmethod
    def malformed(cls, detail: str = "Malformed token.") -> InvalidTokenError:
        return cls(detail)

    @classmethod
    def unresolvable_key(cls) -> InvalidTokenError:
        return cls("Unable to resolve JWKS public key.")

    @classmethod
    def claim_mismatch(cls, claim: str) -> InvalidTokenError:
        return cls(f"JWT claim '{claim}' does not match this application.")

    @classmethod
    def missing_claim(cls, claim: str) -> InvalidTokenError:
        return cls(f"JWT is missing required claim '{claim}'.")


class CodeExchangeError(SsoAuthError):
    """Authorization-code → token exchange failed."""

    @classmethod
    def transport_failed(cls, detail: str = "IdP unreachable.") -> CodeExchangeError:
        return cls(detail)

    @classmethod
    def idp_rejected(cls, detail: str = "IdP rejected the authorization code.") -> CodeExchangeError:
        return cls(detail)

    @classmethod
    def invalid_response(cls) -> CodeExchangeError:
        return cls("IdP returned an invalid token response.")


class UserNotProvisionedError(SsoAuthError):
    """Local user does not exist and JWT ``createUser`` is false."""

    def __init__(self, email: str) -> None:
        super().__init__(f"User '{email}' is not provisioned for this application.")
        self.email = email
