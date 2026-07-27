# baaboo-sso-auth

**Consumer** Python library for integrating internal tools with [baaboo SSO](https://github.com/asheek21-baaboo) — the Python counterpart to the Laravel Composer package [`laravel-auth-package`](https://github.com/asheek21-baaboo/laravel-auth-package).

This package does **not** implement the Identity Provider. It talks **to** the existing IdP:

- Redirect browser to IdP `/oauth/authorize`
- Handle app `GET /oauth/callback`
- Exchange code at IdP `POST /oauth/token` (server-side; `client_secret` never leaves the backend)
- Verify JWTs via IdP JWKS
- Protect routes, expose `CurrentUser`, `/me`, heartbeat **client**, session-end **client**

## Install

Not on PyPI — install directly from GitHub (pin a tag in requirements files):

```bash
pip install "baaboo-sso-auth[fastapi] @ git+https://github.com/asheek21-baaboo/python-auth-package.git@v0.1.0"
# or for local development on this repo:
pip install -e ".[fastapi,dev]"
```

Optional extras: `[fastapi]`, `[flask]`.

## Environment

```env
SSO_BASE_URL=https://sso.example.com
SSO_PROJECT_ID=your-tool-slug
SSO_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
SSO_CLIENT_SECRET=server-only-secret
APP_URL=https://your-tool.example.com
SSO_REDIRECT_AFTER_LOGIN=/
SSO_REDIRECT_TO_IDP_LOGOUT=true
```

`IDP_URL` is accepted as an alias for `SSO_BASE_URL` (Laravel package parity).

**Never** put `SSO_CLIENT_SECRET` in frontend code, browser bundles, or npm env.

Redirect URI registered on the IdP must be `{APP_URL}/oauth/callback`.

## FastAPI quickstart

```python
from fastapi import Depends, FastAPI
from baaboo_sso_auth.fastapi import create_sso_router, require_user
from baaboo_sso_auth.claims import CurrentUser

app = FastAPI()
app.include_router(create_sso_router(
    permissions_resolver=lambda claims: ["reports.view"] if claims.project_role != "admin" else ["*"],
))

@app.get("/dashboard")
def dashboard(user: CurrentUser = Depends(require_user)):
    return {"email": user.email(), "role": user.role()}
```

Routes provided by the router (same paths as the Laravel package):

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/login` | Redirect to IdP authorize |
| `GET` | `/oauth/callback` | Code → token → httpOnly `token` cookie |
| `POST` | `/logout` | IdP `session/end` + clear cookie |
| `GET` | `/oauth/token-expired` | Browser expired-token page |
| `GET` | `/oauth/error` | Shared error stubs |
| `GET` | `/me` | `{ "data": { "name", "role", "permissions" } }` |

Cookie: name `token`, httpOnly, SameSite=Lax, 10 hours.

## Flask quickstart

```python
from flask import Flask, g
from baaboo_sso_auth.flask import create_sso_blueprint, require_auth

app = Flask(__name__)
app.register_blueprint(create_sso_blueprint())

@app.get("/dashboard")
@require_auth
def dashboard():
    return {"email": g.current_user.email()}
```

## Core API (framework-agnostic)

```python
from baaboo_sso_auth import (
    SsoSettings,
    JwtValidator,
    TokenExchanger,
    IdpSessionClient,
    build_authorize_url,
    build_me_response,
    sync_user,
)

settings = SsoSettings()  # from env
url = build_authorize_url(settings)
jwt = TokenExchanger(settings).exchange(code)
claims = JwtValidator(settings).validate(jwt)
IdpSessionClient(settings).heartbeat(jwt)
IdpSessionClient(settings).end_session(jwt)
```

## `/me` contract

```json
{
  "data": {
    "name": "user@company.com",
    "role": "manager",
    "permissions": ["reports.view"]
  }
}
```

- `role` defaults to JWT `project_role`
- `permissions` come from your app (resolver hook); default is `["*"]` for `admin`, else `[]`
- Set `wrap_me_data=False` on the router if you need the flat Laravel `MeController` shape

## Security

- JWT only in httpOnly cookies (or `Authorization: Bearer` for APIs) — never `localStorage`
- Token exchange and `client_secret` are server-only
- Heartbeat `401` / closed IdP session should be treated as logged out

## Docs for AI agents

- Backend (FastAPI/Flask): [`docs/prompts/INTEGRATE_PYTHON_SSO_PACKAGE.md`](docs/prompts/INTEGRATE_PYTHON_SSO_PACKAGE.md)
- Next.js frontend talking to that backend: [`docs/prompts/INTEGRATE_NEXTJS_FRONTEND.md`](docs/prompts/INTEGRATE_NEXTJS_FRONTEND.md)

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## License

Proprietary — internal baaboo use.
