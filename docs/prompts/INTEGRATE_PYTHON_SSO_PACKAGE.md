# Python SSO integration prompt

`baaboo-sso-auth` — wire company SSO into an existing internal Python tool (FastAPI preferred; Flask supported).

> **Scope:** This is a **consumer client library** (same role as `laravel-auth-package`). It does **not** implement the IdP. The IdP remains `baaboo-sso`. Do not add login/2FA UI, JWT signing, authorize issuance, or JWKS hosting in the consuming app.

## Copy-paste into your agent

Open the **consuming Python app** in Cursor, then paste:

> Follow `docs/prompts/INTEGRATE_PYTHON_SSO_PACKAGE.md` end to end. Interview me for install settings — including whether a separate browser frontend (e.g. Next.js) sits in front of this backend, and if so which topology (proxy/rewrite vs separate same-site hosts). Install `baaboo-sso-auth`, copy the SSO `.env` keys, wire protected routes with `require_user` (FastAPI) or `require_auth` (Flask), and verify the login flow against the existing IdP.

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
5. Ask whether a **separate browser frontend** (e.g. Next.js) sits in front of this backend, and if so, which topology — this changes what `APP_URL` and `SSO_REDIRECT_AFTER_LOGIN` mean (see Phase 2). The frontend side is covered by `INTEGRATE_NEXTJS_FRONTEND.md` in this repo; both integrations must agree on the topology.

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

The package is **not on PyPI** — it is installed directly from GitHub:
[`asheek21-baaboo/python-auth-package`](https://github.com/asheek21-baaboo/python-auth-package).

```bash
# latest main (quick dev only)
pip install "baaboo-sso-auth[fastapi] @ git+https://github.com/asheek21-baaboo/python-auth-package.git"

# pinned to a release tag (use this everywhere else)
pip install "baaboo-sso-auth[fastapi] @ git+https://github.com/asheek21-baaboo/python-auth-package.git@v0.1.0"

# Flask instead of FastAPI: swap the extra
pip install "baaboo-sso-auth[flask] @ git+https://github.com/asheek21-baaboo/python-auth-package.git@v0.1.0"
```

In the consuming app's `requirements.txt`:

```text
baaboo-sso-auth[fastapi] @ git+https://github.com/asheek21-baaboo/python-auth-package.git@v0.1.0
```

Or in its `pyproject.toml`:

```toml
dependencies = [
    "baaboo-sso-auth[fastapi] @ git+https://github.com/asheek21-baaboo/python-auth-package.git@v0.1.0",
]
```

Rules:

- **Always pin a tag** (`@v0.1.0`) in requirements files and deploys — never track `main`, or a push to the package repo silently changes what production installs.
- Upgrading = bump the tag and reinstall (`pip install --force-reinstall` if the version number did not change).
- If the repo is **private**, git auth is required at install time: SSH (`git+ssh://git@github.com/asheek21-baaboo/python-auth-package.git@v0.1.0`) for developer machines, or a fine-grained PAT with read-only contents scope for CI/servers (inject via env — never commit a token into a requirements file).

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

#### `APP_URL` depends on the deployment topology

If a separate browser frontend sits in front of this backend, `APP_URL` must be the URL **the browser uses to reach the OAuth callback** — matching the topology chosen in `INTEGRATE_NEXTJS_FRONTEND.md`:

| Topology | `APP_URL` | `SSO_REDIRECT_AFTER_LOGIN` | Backend CORS |
|----------|-----------|----------------------------|--------------|
| Standalone tool (backend serves the UI) | the tool's own URL | relative path (e.g. `/dashboard`) | not needed |
| Option A — frontend proxies to backend via rewrites | the **frontend** URL (e.g. `https://reports.baaboo.com`) | relative path — same origin | not needed |
| Option B — separate same-site hosts | the **backend** URL (e.g. `https://reports-api.baaboo.com`) | **absolute** frontend URL (e.g. `https://reports.baaboo.com/dashboard`) | required (see below) |

Option B additionally requires credentialed CORS on the backend, allowlisting the exact frontend origin (wildcard `*` does not work with credentials):

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://reports.baaboo.com"],  # dev: "http://localhost:3000"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

The `token` cookie is `SameSite=Lax`, so frontend and backend must be **same-site** (same registrable domain; ports ignored). Unrelated domains are not supported — use Option A.

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
- [ ] `APP_URL` matches the deployment topology (standalone / Option A frontend URL / Option B backend URL — see Phase 2)
- [ ] No duplicate `/login` / `/logout` / `/oauth/callback`
- [ ] IdP redirect URI = `{APP_URL}/oauth/callback`
- [ ] Login: IdP → callback → `token` cookie → `SSO_REDIRECT_AFTER_LOGIN`
- [ ] (Option B only) credentialed CORS allowlists the exact frontend origin
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
| Frontend fetches always 401 despite login | Topology mismatch: `APP_URL` points at the wrong host, or frontend/backend are cross-site — re-check the Phase 2 table |
| CORS error from the frontend (Option B) | Allowlist the exact frontend origin with `allow_credentials=True`; wildcard `*` does not work with credentials |

---

### Output format (when you finish)

1. **Topology** — standalone, Option A, or Option B, with the URLs involved  
2. **Discovery** — what auth existed and what you removed  
3. **Files changed** — list with one-line reason  
4. **`.env` keys added** — names only  
5. **Commands run**  
6. **Manual steps left** — IdP registry, deploy env, first login URL  
7. **Verification** — checklist pass/fail  

**Related:** Next.js frontend for this backend — `INTEGRATE_NEXTJS_FRONTEND.md` in this repo; Laravel sibling — `INTEGRATE_LARAVEL_SSO_PACKAGE.md` in `laravel-auth-package`.
