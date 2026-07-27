"""Shared OAuth error stubs (mirrors Laravel ``company-auth.errors``)."""

from __future__ import annotations

ERROR_STUBS: dict[str, dict[str, str]] = {
    "fallback": {
        "message": "Token Expired",
        "description": "The token has expired. Please log in again.",
    },
    "access_denied": {
        "message": "Access denied",
        "description": "You do not have permission to use this application.",
    },
    "sign_in_failed": {
        "message": "Sign-in failed",
        "description": "We could not complete sign-in. Please try again.",
    },
    "user_not_provisioned": {
        "message": "Account not available",
        "description": (
            "Your account is not set up for this application. Contact your administrator."
        ),
    },
    "logged_out": {
        "message": "Logged out",
        "description": "You have been logged out. Please log in again.",
    },
    "unauthenticated": {
        "message": "Unauthenticated",
        "description": "Please log in again.",
    },
}


def resolve_error_stub(stub: str | None) -> dict[str, str]:
    if stub and stub in ERROR_STUBS:
        return ERROR_STUBS[stub]
    return ERROR_STUBS["fallback"]
