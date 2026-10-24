# Dashboard

Auspex's control and research interface: Next.js 16 (App Router), React 19, Tailwind 4. It runs as the `dashboard` service in the compose `app` profile on `http://localhost:${DASHBOARD_PORT}`.

Commands: [AGENTS.md](AGENTS.md).

## How it reaches the backend

The browser calls only the dashboard's own server, whose route handlers under `src/app/api/` forward to core-hub, the scraper and price-service. The routes, the session, the write token and the error shape are owned by [docs/dashboard.md](../../docs/dashboard.md).

## Layout

| Path | Holds |
|---|---|
| `src/app/` | pages and route handlers |
| `src/proxy.ts` | the session check |
| `src/lib/` | the backend-for-frontend, the typed client (`api.ts`), the session |
| `src/__tests__/` | unit and component tests |
| `scripts/hash-password.mjs` | prints the password hash for `.env` ([SETUP.md](../../SETUP.md) step 1 shows how) |
| `.env.local.example` | the variables for a dev server outside the stack |

## Configuration

| Variable | Purpose |
|---|---|
| `CORE_HUB_URL`, `SCRAPER_API_URL`, `PRICE_API_URL` | Backend base URLs, under the same names as in the root `.env` |
| `CORE_HUB_WRITE_TOKEN` | Bearer token core-hub takes on writes |
| `DASHBOARD_USERNAME`, `DASHBOARD_PASSWORD_HASH` | The one login |
| `DASHBOARD_SESSION_SECRET` | HMAC key for the session cookie |
| `DASHBOARD_SESSION_IDLE_MINUTES` | Idle expiry |
