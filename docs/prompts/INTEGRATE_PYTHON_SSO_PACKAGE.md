# Python SSO integration prompt

`baaboo-sso-auth` — wire company SSO into an existing internal Python tool (FastAPI preferred; Flask supported).

> **Scope:** This is a **consumer client library** (same role as `laravel-auth-package`). It does **not** implement the IdP. The IdP remains `baaboo-sso`. Do not add login/2FA UI, JWT signing, authorize issuance, or JWKS hosting in the consuming app.

## Copy-paste into your agent

Open the **consuming Python app** in Cursor, then paste:

> Follow `docs/prompts/INTEGRATE_PYTHON_SSO_PACKAGE.md` end to end. Interview me for install settings, install `baaboo-sso-auth`, copy the SSO `.env` keys, wire protected routes with `require_user` (FastAPI) or `require_auth` (Flask), and verify the login flow against the existing IdP.

---

You are integrating **company SSO** into an **internal Python tool** using:

| Item | Value |
|------|--------|
| Package | `baaboo-sso-auth` |
| Import root | `baaboo_sso_auth` |
| FastAPI auth dependency | `require_user` |
| Flask decorator | `require_auth` |
| Cookie | `token` (httpOnly, SameSite=Lax, 10h) |

The package **owns** JWT validation (via IdP JWKS), OAuth callback, login redirect to the IdP, logout/session-end client, heartbeat client, and `/me`. **Do not reimplement** token parsing, signature verification, or duplicate auth routes.

### Before changing any file

1. Read the package **README.md**.
2. Confirm IdP contract: IdP `docs/ai-sso-auth-and-package-integration.md` (in `baaboo-sso`) if available.
3. Inspect the consuming app: existing `/login`, `/logout`, `/oauth/callback`, session auth, JWT middleware.
4. Ask the human for **`SSO_PROJECT_ID`**, **`SSO_CLIENT_SECRET`**, **`SSO_BASE_URL`**, and **`APP_URL`**. Do not invent secrets.

**Working directory:** the **consuming app root**, not this package repo (unless editing the package itself).

---

### Product rules (do not violate)

| Rule | Detail |
|------|--------|
| Single `/login` | Package router registers `GET /login` → IdP authorize. Remove conflicting app routes. |
| Single `/logout` | Package registers `POST /logout`. |
| No duplicate OAuth paths | Package provides `/oauth/callback`, `/oauth/token-expired`, `/oauth/error`. |
| Protected routes | Use `require_user` / `require_auth` — not ad-hoc JWT decode. |
| JWT in browser | **Forbidden** in JS. SPAs use `GET /me` with cookies (`credentials: 'include'`). |
| Cookie | Name `token`, httpOnly — set by package callback only. |
| IdP redirect URI | Must be `{APP_URL}/oauth/callback`. |
| No IdP code | Do not mint JWTs, host JWKS, or implement `/oauth/token` in the app. |

---

### Phase 1 — Install

```bash
pip install baaboo-sso-auth
# or: pip install "baaboo-sso-auth[fastapi]"
# private VCS example:
# pip install "git+https://github.com/your-org/baaboo-python-auth-package.git"
```

---

### Phase 2 — Environment

Append to `.env` / `.env.example` (placeholders only in example):

```env
SSO_BASE_URL=https://sso.example.com
SSO_PROJECT_ID=your-tool-slug
SSO_CLIENT_ID=your-tool-slug
SSO_CLIENT_SECRET=from-idp-registry
APP_URL=https://your-tool.example.com
SSO_REDIRECT_AFTER_LOGIN=/dashboard
SSO_REDIRECT_TO_IDP_LOGOUT=true
```

Local alias (Laravel parity): `IDP_URL` may override base URL when developing against a local IdP.

Register on the IdP:

- `project_id` = `SSO_PROJECT_ID`
- Redirect URI = `{APP_URL}/oauth/callback`

---

### Phase 3 — Remove conflicting auth

| Find | Action |
|------|--------|
| App `GET /login` password form | Remove or replace with SSO login |
| App `GET /oauth/callback` | Delete — package owns it |
| Custom JWT middleware duplicating JWKS verify | Prefer package dependency |
| Secrets in frontend | Remove `SSO_CLIENT_SECRET` from any browser env |

---

### Phase 4 — Wire FastAPI

```python
from fastapi import Depends, FastAPI
from baaboo_sso_auth.fastapi import create_sso_router, require_user
from baaboo_sso_auth.claims import CurrentUser

app = FastAPI()
app.include_router(create_sso_router(
    permissions_resolver=lambda c: ["*"] if c.project_role == "admin" else ["reports.view"],
))

@app.get("/dashboard")
def dashboard(user: CurrentUser = Depends(require_user)):
    return {"id": user.id(), "email": user.email(), "role": user.role()}
```

### Phase 4b — Wire Flask

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

---

### Phase 5 — Optional createUser provisioning

If JWT `createUser` is true and the app has a local user table, pass hooks:

```python
def find_by_email(email: str): ...
def upsert_user(claims): ...

app.include_router(create_sso_router(
    find_by_email=find_by_email,
    upsert_user=upsert_user,
))
```

When `createUser` is false and the user is missing locally → redirect `user_not_provisioned` error stub.

---

### Phase 6 — Verification checklist

- [ ] Package installed; imports resolve
- [ ] `.env` has `SSO_*` + `APP_URL`
- [ ] No duplicate `/login` / `/logout` / `/oauth/callback`
- [ ] IdP redirect URI = `{APP_URL}/oauth/callback`
- [ ] Login: IdP → callback → `token` cookie → `SSO_REDIRECT_AFTER_LOGIN`
- [ ] Protected route returns user via `require_user` / `require_auth`
- [ ] `GET /me` returns `{ "data": { "name", "role", "permissions" } }`
- [ ] Logout clears cookie and calls IdP `/oauth/session/end` when enabled
- [ ] `SSO_CLIENT_SECRET` never in frontend

---

### What NOT to do

- Do not build an IdP (no token signing, no JWKS issuer, no authorize code minting).
- Do not store JWTs in `localStorage`.
- Do not call `/oauth/token` from the browser.
- Do not commit real `SSO_CLIENT_SECRET` values.

---

### Troubleshooting

| Symptom | Likely fix |
|---------|------------|
| `401 Unauthenticated` | Hit `/login` → IdP → callback |
| `403` on callback | Wrong secret, `aud`, or redirect URI mismatch |
| `/me` missing `data` wrapper | Ensure `wrap_me_data=True` (default) |
| Heartbeat 401 | Treat as logout; clear cookie |

---

### Output format (when you finish)

1. **Discovery** — what auth existed and what you removed  
2. **Files changed** — list with one-line reason  
3. **`.env` keys added** — names only  
4. **Commands run**  
5. **Manual steps left** — IdP registry, deploy env, first login URL  
6. **Verification** — checklist pass/fail  

**Related:** Next.js frontend for this backend — `INTEGRATE_NEXTJS_FRONTEND.md` in this repo; Laravel sibling — `INTEGRATE_LARAVEL_SSO_PACKAGE.md` in `laravel-auth-package`.
