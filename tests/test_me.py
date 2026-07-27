"""``/me`` response shape tests."""

from __future__ import annotations

from baaboo_sso_auth.claims import CurrentUser, SsoClaims
from baaboo_sso_auth.me import build_me_response


def _claims(**overrides) -> SsoClaims:
    base = dict(
        sub="u1",
        email="a@b.com",
        project_role="manager",
        project_id="demo-app",
        aud="demo-app",
        iss="https://sso.test",
        jti="j1",
        global_role="staff",
        create_user=False,
    )
    base.update(overrides)
    return SsoClaims(**base)


def test_me_wrapped_shape() -> None:
    payload = build_me_response(CurrentUser(_claims()))
    assert payload == {
        "data": {
            "name": "a@b.com",
            "role": "manager",
            "permissions": [],
        }
    }


def test_me_admin_wildcard() -> None:
    payload = build_me_response(CurrentUser(_claims(project_role="admin")))
    assert payload["data"]["permissions"] == ["*"]


def test_me_custom_permissions_resolver() -> None:
    payload = build_me_response(
        CurrentUser(_claims()),
        permissions=lambda c: ["reports.view", "reports.export"],
    )
    assert payload["data"]["permissions"] == ["reports.view", "reports.export"]


def test_me_flat_laravel_compat() -> None:
    payload = build_me_response(CurrentUser(_claims()), wrap_data=False)
    assert payload == {"name": "a@b.com", "role": "manager", "permissions": []}
