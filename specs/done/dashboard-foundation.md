# Dashboard Foundation

**Status:** done
**Branch:** `feature/dashboard-foundation`

---

## Context

Decided 2026-10-08: the Next.js dashboard (`services/dashboard`) becomes Auspex's control and research interface. It runs as a service in the Docker stack and reaches the backend services through its own server layer, behind a single-user login. Grafana stays the place for technical health.

The 2026-10-08 audit found the dashboard is not operational:
- Next.js 15.3.4, React 19, Tailwind, Vitest + RTL. Pages: ticker search (`/`), watchlist (`/watchlist`), company detail (`/watchlist/[ticker]`). 13 component tests pass and `next build` succeeds.
- No Dockerfile, no compose service, no CI workflow, no run instructions.
- The browser calls core-hub directly through `NEXT_PUBLIC_API_URL` (baked in at build time). core-hub's `WebConfig` allows CORS `GET` only, so every watchlist write (POST, DELETE, PATCH) fails the browser's preflight.
- `npm run lint` stops at an interactive ESLint prompt (no config). `tsc --noEmit` reports 2 errors in `Watchlist.test.tsx`. `npm test` starts watch mode.
- `npm audit`: 15 advisories (4 critical), including `next` 15.3.4 and `sharp`.
- Errors are swallowed (`handleAdd`, `handleRemoveConfirm`, `fetchEntries`); loading states are mostly missing; each component builds its own base URL; the watchlist summary always returns an empty `direct_signals` list (`WatchlistService.java:157`); the UI cannot add a gene target although the PATCH supports `add`.
- No API has auth. All service ports are bound to `127.0.0.1`.

## What this builds

1. **Backend-for-frontend (BFF) in Next.js route handlers** under `src/app/api/`. The browser calls only the dashboard's own origin. Route handlers forward to core-hub, the scraper, price-service and (later) Airflow using server-side env (`CORE_HUB_URL`, `SCRAPER_API_URL`, `PRICE_API_URL`), read at runtime, never `NEXT_PUBLIC_*`. The BFF holds no business logic and touches no datastore: it authenticates, forwards, and normalises errors into one shape `{error: {code, message, upstream_status}}` and list responses into `{items, next_cursor}`.
2. **Single-user login.** Username and an argon2id or bcrypt password hash from `.env` (`DASHBOARD_USERNAME`, `DASHBOARD_PASSWORD_HASH`); a signed, `HttpOnly`, `SameSite=Strict` session cookie (`DASHBOARD_SESSION_SECRET`, idle expiry from `.env`). Middleware rejects every page and `/api/*` route without a valid session, except `/login` and `/api/health`. A helper script prints a hash for a chosen password, documented in `SETUP.md`.
3. **Service token for core-hub writes.** core-hub requires `Authorization: Bearer ${CORE_HUB_WRITE_TOKEN}` on every non-GET `/api/**` request; the BFF sends it. CORS mappings are removed from core-hub, since no browser calls it any more.
4. **Container:** a multi-stage Dockerfile (`output: 'standalone'`, Node 22 runtime image pinned in VERSIONS.md, non-root user, healthcheck on `/api/health`), a `dashboard` service in the `app` profile on `127.0.0.1:${DASHBOARD_PORT}` (default 3001; Grafana holds 3000), depending on core-hub being healthy.
5. **CI:** `.github/workflows/dashboard.yml` runs `npm ci`, `npm run lint`, `npx tsc --noEmit`, `npm run test:ci` (`vitest run`), `npm run build`, scoped to `services/dashboard/**` changes.
6. **Hygiene:** ESLint flat config (`next/core-web-vitals`, `next/typescript`); the 2 test type errors fixed; `next` and any other package with a high or critical advisory upgraded to a patched exact version (recorded in VERSIONS.md); one typed API client in `src/lib/api.ts` used by every component; loading, empty and error states on every data view; error messages shown to the user; accessible confirm dialog (`role="dialog"`, `aria-modal`, focus trap, Escape closes); `<Link>` for internal navigation.
7. **Existing views made whole:** company detail lists the company's direct signals (core-hub summary populates `direct_signals`) and lets the user add a gene target (PATCH `add`).

## Out of scope

- New views (browse, pipeline control, trace, config, results each have their own spec).
- Multi-user accounts, roles, OAuth.
- Exposing the dashboard beyond localhost. Remote access is a later decision; the cookie and token design does not prevent it.
- Visual redesign beyond consistent Tailwind layout primitives (page shell, table, card, button, form field).

## Constraints

- Invariants 1 and 2: the BFF never writes a datastore and never talks to Kafka, Postgres, Neo4j or MinIO directly.
- Invariant 6: every URL, port, credential and secret from `.env`; `.env.example` documents each. No secret reaches client bundles (checked by a test that greps `.next/static` for each secret's env name and value).
- Invariant 9: timestamps from the API are rendered as UTC with an explicit `UTC` suffix.
- Code comments follow TSDoc conventions (`services/CLAUDE.md`).
- Node 22.x per VERSIONS.md; `.nvmrc` pinned to the exact version.

## Required tests

Dashboard (Vitest), `src/__tests__/`:
- `bff.test.ts`
  - `test_bff_forwards_get_to_core_hub_using_server_side_url`
  - `test_bff_adds_write_token_on_non_get_requests_only`
  - `test_bff_normalises_upstream_error_into_error_shape_with_upstream_status`
  - `test_bff_returns_502_with_error_shape_when_upstream_is_unreachable`
- `auth.test.ts`
  - `test_request_without_session_is_redirected_to_login`
  - `test_api_request_without_session_returns_401`
  - `test_health_route_is_reachable_without_session`
  - `test_correct_credentials_set_httponly_samesite_strict_cookie`
  - `test_wrong_password_returns_401_and_sets_no_cookie`
  - `test_tampered_session_cookie_is_rejected`
  - `test_expired_session_is_rejected`
- `api-client.test.ts`
  - `test_components_call_only_same_origin_api_paths`
- `Watchlist.test.tsx` (existing, extended)
  - `test_failed_add_shows_the_error_message`
  - `test_failed_remove_keeps_the_entry_and_shows_the_error`
  - `test_list_shows_loading_then_entries`
  - `test_confirm_dialog_is_modal_and_closes_on_escape`
- `CompanyDetail.test.tsx`
  - `test_company_detail_lists_direct_signals`
  - `test_gene_target_can_be_added`
- `bundle-secrets.test.ts` (runs after `next build`)
  - `test_no_server_secret_appears_in_client_bundle`

Stack config, `services/ingestion-scraper/tests/unit/test_dashboard_stack_config.py`:
- `test_dashboard_service_is_in_app_profile_bound_to_localhost_with_healthcheck`
- `test_dashboard_service_gets_backend_urls_and_secrets_from_env_only`

core-hub, `src/integrationTest/java/.../rest/WriteTokenIT.java`:
- `writeWithoutTokenIsRejectedWith401`
- `writeWithWrongTokenIsRejectedWith401`
- `writeWithTokenSucceeds`
- `getRequestsNeedNoToken`
- `noCorsHeadersAreReturnedForCrossOriginRequests`

core-hub, `src/integrationTest/java/.../watchlist/WatchlistSummaryIT.java`:
- `summaryIncludesDirectSignalsMentioningTheCompany`

## Definition of done

```bash
cd services/dashboard && npm ci && npm run lint && npx tsc --noEmit && npm run test:ci && npm run build && npx vitest run src/__tests__/bundle-secrets.test.ts
cd services/ingestion-scraper && uv run pytest tests/unit/test_dashboard_stack_config.py -q --strict-markers
cd services/core-hub && ./gradlew integrationTest --tests '*WriteTokenIT' --tests '*WatchlistSummaryIT' --rerun-tasks
docker compose --profile app -f docker/docker-compose.yml --env-file .env up -d --wait
```

Expected: lint and typecheck clean; all dashboard tests pass (13 existing + 19 new, none skipped); 2 stack-config tests and 6 core-hub tests pass; the `dashboard` service is healthy. `npm audit --audit-level=high` reports 0. Then, in a browser at `http://localhost:${DASHBOARD_PORT}`: log in, add a watchlist ticker, add and remove a gene target, remove the ticker, with each change visible after a reload.

## Notes

- Why a BFF instead of fixing CORS: it also keeps the Airflow credentials and the core-hub write token off the browser, joins data across services for the trace view, and gives every view one error and pagination shape. A separate API gateway product is not warranted for one user.
- The write token is defence in depth for a localhost stack: any local process can reach `127.0.0.1:8080`, and config writes change what the pipeline ingests.
