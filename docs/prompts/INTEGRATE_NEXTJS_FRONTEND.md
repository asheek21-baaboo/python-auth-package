# Next.js frontend integration prompt

Wire a **Next.js frontend** to a **FastAPI (or Flask) backend that already uses `baaboo-sso-auth`**.

> **Scope:** The frontend does **no auth work**. Login, OAuth callback, token exchange, JWT validation, the httpOnly `token` cookie, logout, and `/me` are all owned by the backend package. The frontend only: (1) calls the backend with credentials, (2) redirects the browser to the backend `/login` on 401, (3) reads `GET /me` to render name/role/permissions.

## Copy-paste into your agent

Open the **Next.js app** in Cursor, then paste:

> Follow `docs/prompts/INTEGRATE_NEXTJS_FRONTEND.md` (from `baaboo-python-auth-package`) end to end. Before changing files, ask me to choose **Option A (Next.js proxy/rewrite)** or **Option B (separate same-site frontend and backend hosts)** and ask for the frontend/backend dev and production URLs. Wait for my answer, then implement only the selected topology. Add the credentialed fetch wrapper with 401 → `/login` redirect, add the `/me` auth hook, and verify the full login round-trip against the backend.

---

You are integrating a Next.js frontend with a backend that exposes these package-owned routes:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/login` | Browser redirect → IdP authorize (full navigation, **not** fetch) |
| `GET` | `/oauth/callback` | IdP returns here; backend sets httpOnly `token` cookie, then redirects to `SSO_REDIRECT_AFTER_LOGIN` |
| `POST` | `/logout` | Ends IdP session + clears cookie |
| `GET` | `/me` | `{ "data": { "name", "role", "permissions" } }` — 401 when not logged in |

The JWT lives **only** in the httpOnly `token` cookie. The frontend never sees, stores, or forwards it manually.

### Before changing any file

1. Read the backend's SSO setup (confirm `create_sso_router` / `create_sso_blueprint` is wired).
2. Ask the human the topology question in Phase 1 and **wait for an answer**. Do not infer or silently choose a topology.
3. Ask for the **backend URL** (dev + prod) and **frontend URL** (dev + prod).
4. Inspect the Next.js app: existing auth code, token storage, `Authorization` headers, login pages — these will be **removed**.

**Working directory:** the **Next.js app root**, not this package repo.

---

### Product rules (do not violate)

| Rule | Detail |
|------|--------|
| No JWT in JS | Never read, store, or attach the token. No `localStorage`, no `Authorization: Bearer` from the browser. |
| No frontend login UI | No password forms, no NextAuth/Auth.js, no OAuth client in Next.js. The IdP owns login UI. |
| Login is a navigation | `window.location.href = LOGIN_URL` — never `fetch('/login')` (redirects to the IdP cannot be followed by XHR). |
| Credentials on every call | All backend fetches use `credentials: 'include'`. |
| 401 means logged out | Any 401 from the backend → redirect the browser to `/login`. |
| No secrets in frontend | `SSO_CLIENT_SECRET` and other `SSO_*` server keys must never appear in the Next.js repo or `NEXT_PUBLIC_*` env. |

---

### Phase 1 — Choose the topology

The `token` cookie is `SameSite=Lax`, so browser and backend must be **same-site**.

Before editing or installing anything, ask the human:

> Which deployment topology should I implement?
>
> 1. **Option A — Next.js proxy/rewrite (recommended):** the browser uses only the Next.js origin, and Next.js proxies SSO and API requests to FastAPI.
> 2. **Option B — Separate same-site hosts:** Next.js and FastAPI are public on separate hosts under the same registrable domain, requiring credentialed CORS.
>
> Also provide the frontend and backend URLs for development and production.

Wait for the answer. Record the selected topology and URLs, then follow **only that option's** configuration and examples throughout this document:

- **Option A:** configure rewrites and `BACKEND_URL`; keep `NEXT_PUBLIC_API_URL` unset; do not add CORS solely for this integration.
- **Option B:** configure `NEXT_PUBLIC_API_URL` and backend credentialed CORS; do not add Next.js auth/API rewrites.
- If the proposed production hosts are unrelated domains, explain that Option B is incompatible with the package's `SameSite=Lax` cookie and ask the human to choose Option A or change the domains.
- Do not combine both options or leave both active as fallbacks.

#### Option A — Proxy through Next.js rewrites (recommended)

Single origin: the browser only ever talks to the Next.js domain; Next.js proxies auth + API paths to the backend. No CORS. The cookie is set on the Next.js domain, so Next.js middleware and server components can forward it for SSR checks.

```js
// next.config.js
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

module.exports = {
  async rewrites() {
    return [
      { source: "/login", destination: `${BACKEND_URL}/login` },
      { source: "/oauth/:path*", destination: `${BACKEND_URL}/oauth/:path*` },
      { source: "/logout", destination: `${BACKEND_URL}/logout` },
      { source: "/me", destination: `${BACKEND_URL}/me` },
      { source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` },
    ];
  },
};
```

Backend env for this topology:

```env
APP_URL=https://your-frontend.example.com   # the Next.js URL — redirect URI is {APP_URL}/oauth/callback
SSO_REDIRECT_AFTER_LOGIN=/
```

IdP redirect URI registered = `{Next.js URL}/oauth/callback`.

`BACKEND_URL` is a **server-only** env var (no `NEXT_PUBLIC_` prefix).

**Worked example (Option A)** — tool called `reports`, Next.js at `https://reports.baaboo.com`, FastAPI reachable only from the Next.js server at `http://10.0.0.5:8000`:

Frontend `.env` (Next.js — server-only):

```env
BACKEND_URL=http://10.0.0.5:8000        # dev: http://localhost:8000
```

Backend `.env` (FastAPI):

```env
SSO_BASE_URL=https://sso.baaboo.com
SSO_PROJECT_ID=reports
SSO_CLIENT_ID=reports
SSO_CLIENT_SECRET=from-idp-registry
APP_URL=https://reports.baaboo.com      # the FRONTEND URL — dev: http://localhost:3000
SSO_REDIRECT_AFTER_LOGIN=/dashboard     # relative — same origin
```

IdP registry: redirect URI = `https://reports.baaboo.com/oauth/callback` (dev: `http://localhost:3000/oauth/callback`).

Login round-trip as the browser sees it (one origin throughout):

1. User opens `https://reports.baaboo.com/dashboard` → `/me` returns 401 → browser navigates to `https://reports.baaboo.com/login`
2. Next.js proxies `/login` to FastAPI, which responds with a redirect to `https://sso.baaboo.com/oauth/authorize?...`
3. User logs in at the IdP → IdP redirects to `https://reports.baaboo.com/oauth/callback?code=...`
4. Next.js proxies the callback to FastAPI → FastAPI exchanges the code, sets the `token` cookie (which lands on `reports.baaboo.com`), redirects to `/dashboard`
5. All further `/api/*` and `/me` fetches carry the cookie automatically; `NEXT_PUBLIC_API_URL` stays unset so `API_BASE` is `""`

#### Option B — Separate same-site hosts (e.g. `app.example.com` + `api.example.com`)

Same registrable domain counts as same-site, so the Lax cookie still flows — but CORS is required.

- Backend adds CORS middleware: `allow_origins=[frontend origin]`, `allow_credentials=True`.
- Backend env: `APP_URL` = the **backend** URL; `SSO_REDIRECT_AFTER_LOGIN` = the **frontend** URL (absolute).
- IdP redirect URI = `{backend URL}/oauth/callback`.
- Frontend env: `NEXT_PUBLIC_API_URL=https://api.example.com`.
- Dev works the same way: `localhost:3000` → `localhost:8000` is same-site (ports are ignored by SameSite).

**Worked example (Option B)** — tool called `reports`, Next.js at `https://reports.baaboo.com`, FastAPI publicly at `https://reports-api.baaboo.com` (same registrable domain `baaboo.com` → same-site):

Frontend `.env` (Next.js):

```env
NEXT_PUBLIC_API_URL=https://reports-api.baaboo.com   # dev: http://localhost:8000
```

Backend `.env` (FastAPI):

```env
SSO_BASE_URL=https://sso.baaboo.com
SSO_PROJECT_ID=reports
SSO_CLIENT_ID=reports
SSO_CLIENT_SECRET=from-idp-registry
APP_URL=https://reports-api.baaboo.com                    # the BACKEND URL — dev: http://localhost:8000
SSO_REDIRECT_AFTER_LOGIN=https://reports.baaboo.com/dashboard  # absolute — different host; dev: http://localhost:3000/dashboard
```

Backend CORS (FastAPI):

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

IdP registry: redirect URI = `https://reports-api.baaboo.com/oauth/callback` (dev: `http://localhost:8000/oauth/callback`).

Login round-trip as the browser sees it (two hosts, one site):

1. User opens `https://reports.baaboo.com/dashboard` → fetch to `https://reports-api.baaboo.com/me` returns 401 → browser navigates to `https://reports-api.baaboo.com/login`
2. FastAPI redirects to `https://sso.baaboo.com/oauth/authorize?...`
3. User logs in at the IdP → IdP redirects to `https://reports-api.baaboo.com/oauth/callback?code=...`
4. FastAPI exchanges the code, sets the `token` cookie (which lands on `reports-api.baaboo.com`), redirects to `https://reports.baaboo.com/dashboard`
5. Further fetches from the frontend to `reports-api.baaboo.com` carry the cookie because the hosts are same-site and every fetch uses `credentials: 'include'`

**Not supported:** unrelated domains (e.g. `*.vercel.app` frontend + different backend domain). `SameSite=Lax` blocks the cookie cross-site. Use Option A instead.

---

### Phase 2 — Remove conflicting auth

| Find | Action |
|------|--------|
| Token stored in `localStorage` / cookies set by JS / React state | Delete — cookie is httpOnly, browser-managed |
| `Authorization: Bearer` headers built in frontend code | Delete — credentials ride the cookie |
| Custom login page / password form | Delete — `/login` navigates to the IdP |
| NextAuth / Auth.js / custom OAuth client | Remove — the backend package is the OAuth client |
| Backend token-minting endpoint created just for the frontend | Remove from the backend — the package owns tokens |

---

### Phase 3 — Fetch wrapper

All backend calls go through one wrapper: send credentials, treat 401 as logged out.

```ts
// lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ""; // "" when using rewrites (Option A)

export const LOGIN_URL = `${API_BASE}/login`;

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
  });
  if (res.status === 401 && typeof window !== "undefined") {
    window.location.href = LOGIN_URL; // full navigation → IdP round-trip
  }
  return res;
}
```

---

### Phase 4 — Auth hook / user context

```tsx
// lib/use-user.ts
"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "./api";

export type User = { name: string; role: string; permissions: string[] };

export function useUser() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch("/me")
      .then(async (res) => {
        if (res.ok) {
          const body = await res.json();
          setUser(body.data); // { name, role, permissions }
        }
      })
      .finally(() => setLoading(false));
  }, []);

  return { user, loading };
}
```

Gate pages on `user` being present; while `loading`, render nothing or a spinner. On 401 the wrapper has already redirected to `/login`.

Permission checks in the UI are cosmetic only (`user.permissions.includes("reports.view")` to hide buttons); the backend enforces the real rules via `require_user`.

---

### Phase 5 — Logout

```ts
export async function logout() {
  await apiFetch("/logout", { method: "POST" });
  window.location.href = "/"; // backend cleared the cookie and ended the IdP session
}
```

---

### Phase 6 — Optional SSR protection (Option A only)

With rewrites, the `token` cookie lives on the Next.js domain, so `middleware.ts` can gate routes before render:

```ts
// middleware.ts
import { NextResponse, type NextRequest } from "next/server";

export function middleware(req: NextRequest) {
  if (!req.cookies.has("token")) {
    return NextResponse.redirect(new URL("/login", req.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!login|oauth|logout|me|api|_next|favicon.ico).*)"],
};
```

This only checks **presence** — do not decode or verify the JWT in Next.js. Validation stays on the backend (an expired cookie will simply 401 on the first API call and bounce through `/login`).

Server components can forward the cookie when fetching:

```ts
import { cookies } from "next/headers";

const res = await fetch(`${process.env.BACKEND_URL}/me`, {
  headers: { cookie: cookies().toString() },
  cache: "no-store",
});
```

Not applicable to Option B: the cookie belongs to the backend host, so the Next.js server never sees it — gate client-side via `useUser`.

---

### Phase 7 — Verification checklist

- [ ] No token in `localStorage`, JS-readable cookies, or `Authorization` headers
- [ ] No `SSO_*` secrets anywhere in the frontend repo
- [ ] Visiting a protected page while logged out ends up at the IdP login screen
- [ ] After IdP login, browser lands back on the frontend, logged in
- [ ] `GET /me` returns `{ "data": { "name", "role", "permissions" } }` and the UI shows them
- [ ] Authenticated API calls to the backend succeed with no manual headers
- [ ] Logout clears the session; next protected action redirects to `/login`
- [ ] (Option A) IdP redirect URI = `{frontend URL}/oauth/callback`; (Option B) = `{backend URL}/oauth/callback`

---

### What NOT to do

- Do not install NextAuth/Auth.js or implement any OAuth flow in Next.js.
- Do not read, decode, verify, or store the JWT in frontend code.
- Do not call `/login` or `/oauth/*` with `fetch` — always full browser navigation.
- Do not deploy frontend and backend on unrelated domains and expect the cookie to flow.
- Do not put `SSO_CLIENT_SECRET` or the backend `.env` keys in the Next.js project.

---

### Troubleshooting

| Symptom | Likely fix |
|---------|------------|
| `/me` always 401 even after login | Missing `credentials: 'include'`, or frontend/backend are cross-site (check topology) |
| CORS error on fetch (Option B) | Backend CORS must allowlist the exact frontend origin and set `allow_credentials=True`; wildcard `*` origins do not work with credentials |
| Login "does nothing" | `/login` was called with `fetch` instead of `window.location.href` |
| Redirect loop through `/login` | Cookie not being set: redirect URI mismatch on the IdP, or callback served from a different host than the one the browser uses |
| Cookie missing in dev | Use `http://localhost` for both apps (not a mix of `localhost` and `127.0.0.1` — those are different sites) |
| Works in dev, breaks deployed | Frontend and backend are not same-site in prod; switch to Option A rewrites |

---

### Output format (when you finish)

1. **Topology chosen** — Option A or B, with the URLs involved
2. **Discovery** — what frontend auth existed and what you removed
3. **Files changed** — list with one-line reason
4. **Env keys added** — names only, frontend and backend
5. **Manual steps left** — IdP redirect URI, deploy env
6. **Verification** — checklist pass/fail

**Related:** backend side — `INTEGRATE_PYTHON_SSO_PACKAGE.md` in this repo; Laravel sibling — `INTEGRATE_LARAVEL_SSO_PACKAGE.md` in `laravel-auth-package`.
