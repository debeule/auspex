# Dashboard

Auspex's control and research interface: Next.js 16 (App Router), React 19, Tailwind 4. It runs as the `dashboard` service in the compose `app` profile on `http://localhost:${DASHBOARD_PORT}` (default 3001; Grafana has 3000).

## How it reaches the backend

The browser calls only the dashboard's own origin. Route handlers under `src/app/api/` hold no business logic and touch no datastore:

| Route | Does |
|---|---|
| `/api/health` | Liveness for the container healthcheck. No session needed. |
| `/api/auth/login`, `/api/auth/logout` | Single-user sign-in: checks `DASHBOARD_USERNAME` and the bcrypt `DASHBOARD_PASSWORD_HASH`, sets or clears the signed `auspex_session` cookie (`HttpOnly`, `SameSite=Strict`). |
| `/api/core-hub/<path>` | Forwards to `${CORE_HUB_URL}/api/<path>`; adds `Authorization: Bearer ${CORE_HUB_WRITE_TOKEN}` on every non-GET request. |
| `/api/scraper/<path>`, `/api/prices/<path>` | Forward to `${SCRAPER_API_URL}` and `${PRICE_API_URL}`. |

Every error comes back as `{error: {code, message, upstream_status}}`; a JSON array comes back as `{items, next_cursor}`. An unreachable or failing upstream is a 502. `src/proxy.ts` (Next 16's name for middleware) admits only signed-in requests: pages redirect to `/login`, API routes answer 401. Each request re-issues the cookie, so the session ends after `DASHBOARD_SESSION_IDLE_MINUTES` without activity.

Components call the backend only through `src/lib/api.ts`. Backend URLs and secrets are server-side env read per request, never `NEXT_PUBLIC_*`; `bundle-secrets.test.ts` checks the built client bundle for each of them.

## Configuration

| Variable | Purpose |
|---|---|
| `CORE_HUB_URL`, `SCRAPER_API_URL`, `PRICE_API_URL` | Backend base URLs, under the same names as in the root `.env`. |
| `CORE_HUB_WRITE_TOKEN` | Bearer token core-hub requires on writes. |
| `DASHBOARD_USERNAME`, `DASHBOARD_PASSWORD_HASH` | The one login. Generate the hash as `SETUP.md` shows. |
| `DASHBOARD_SESSION_SECRET` | HMAC key for the session cookie. |
| `DASHBOARD_SESSION_IDLE_MINUTES` | Idle expiry (default 30). |

## Commands

| Purpose | Command |
|---|---|
| Install | `npm ci` |
| Lint | `npm run lint` |
| Type check | `npx tsc --noEmit` |
| Tests (unit + component) | `npm run test:ci` |
| Build | `npm run build` |
| Client bundle secret check (after a build, same env) | `npm run test:bundle` |
| Dev server outside the stack | `cp .env.local.example .env.local`, fill it in, `npm run dev` |
| Password hash | `npm run hash-password` (reads the password from stdin) |

CI (`.github/workflows/dashboard.yml`) runs all of the above, audits runtime dependencies, then builds the image and checks health, the login and the session gate against the running container.
