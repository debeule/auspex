# Dashboard

Domain: DSH · Code: `services/dashboard/src/`, `services/dashboard/scripts/hash-password.mjs` · Last reviewed against: develop @ `b7582c3`

## Scope

The dashboard is the application's own interface: the pages a user works in, the single-user login, and the server layer (BFF) through which the browser reaches the backend services. Settings are environment variables listed in `.env.example` (block "Dashboard") and named here only.

- Technical health (service status, resource use, logs and alerts) is Grafana's, not the dashboard's: see [observability.md](operations/observability.md).
- The core-hub half of the server layer's security is owned by [`docs/core-hub/http-api.md`](core-hub/http-api.md): the bearer token core-hub requires on writes ([HUB-041](core-hub/http-api.md#HUB-041)) and its refusal of CORS ([HUB-043](core-hub/http-api.md#HUB-043)). This file states only the dashboard's half, DSH-009.
- Research config is shown read-only ([EVA-006](research/evaluation-protocol.md#EVA-006)).
- The strategy runtime's metrics API is not reachable from the dashboard: the BFF has no strategy upstream ([STR-039](strategy/runtime.md#STR-039)).
- Proposed views (signal browsing, pipeline control, lineage, ingestion config, research results) stay in their specs until they are built.

Not in this file: the dashboard container, its port and memory limit ([topology.md](operations/topology.md)); its CI checks ([verification.md](engineering/verification.md)).

## Requirements

*Boundaries.*
- <a id="DSH-001"></a>**DSH-001** — The dashboard shows what the application found and lets the user act on it; it has no page for service health, resource use or logs.
- <a id="DSH-002"></a>**DSH-002** — The browser calls only the dashboard's own origin. Route handlers forward to a backend service through the BFF and hold no business logic; the dashboard touches no datastore.

*Login and sessions.*
- <a id="DSH-003"></a>**DSH-003** — Login is single-user: a name equal to `DASHBOARD_USERNAME` and a password matching the bcrypt `DASHBOARD_PASSWORD_HASH`, which `scripts/hash-password.mjs` produces as a single-quoted `.env` line and refuses for an empty password. Wrong credentials get 401 and no cookie.
- <a id="DSH-004"></a>**DSH-004** — A session is a cookie signed with HMAC-SHA256 under `DASHBOARD_SESSION_SECRET`, `HttpOnly` and `SameSite=Strict`, and `Secure` only when the request arrived over HTTPS. It expires after `DASHBOARD_SESSION_IDLE_MINUTES` without activity and is re-issued on every admitted request; a tampered cookie, an expired one or one issued to a name other than the configured username is rejected.
- <a id="DSH-005"></a>**DSH-005** — Only `/login`, `/api/health` and `/api/auth/login` are reachable without a session. Logout clears the session cookie.
- <a id="DSH-006"></a>**DSH-006** — `src/proxy.ts` is the only authorization point. A page request without a valid session is redirected to `/login` with `next` set to the requested path, an API request gets 401 in the error shape, and after sign-in a `next` on another origin is ignored.

*The server layer.*
- <a id="DSH-007"></a>**DSH-007** — One route handler forwards `/api/<service>/<path>` to the named upstream: `core-hub` (mounted under its `/api` prefix, so its actuator endpoints are out of reach), `scraper` or `prices`, each at a base URL read from its environment variable on every request. An unknown service gets 404 without an upstream call; an upstream whose URL is not set gets 503.
- <a id="DSH-008"></a>**DSH-008** — The BFF forwards only the `accept` and `content-type` headers; the browser's `cookie` and `authorization` headers never reach an upstream.
- <a id="DSH-009"></a>**DSH-009** — On every core-hub request whose method is not GET or HEAD, the BFF sends `CORE_HUB_WRITE_TOKEN` as a bearer token, the header core-hub requires under [HUB-041](core-hub/http-api.md#HUB-041) in `docs/core-hub/http-api.md`; on reads it sends none.
- <a id="DSH-010"></a>**DSH-010** — Every BFF error is `{error: {code, message, upstream_status}}`. An upstream 4xx passes through with its status; an upstream 5xx, or an upstream that cannot be reached, becomes 502.
- <a id="DSH-011"></a>**DSH-011** — A JSON array from an upstream is returned as `{items, next_cursor}`, and a 204 passes through without a body.
- <a id="DSH-012"></a>**DSH-012** — The BFF never forwards a request to a path outside the upstream's base path.

*The client.*
- <a id="DSH-013"></a>**DSH-013** — No server secret or backend URL reaches the client bundle, and no backend setting is a `NEXT_PUBLIC_*` variable.
- <a id="DSH-014"></a>**DSH-014** — Components reach the backend only through the typed client in `src/lib/api.ts`, on same-origin `/api` paths, and the client raises the BFF's error message.

*Awaiting ratification.*
- <a id="DSH-015"></a>**DSH-015** — The BFF abandons an upstream request after a fixed timeout and answers 502 as for an unreachable upstream.
- <a id="DSH-016"></a>**DSH-016** — The credential check compares the password hash even when the username is wrong, so a wrong name and a wrong password take the same time.
- <a id="DSH-017"></a>**DSH-017** — Writes to the scraper and the price service are forwarded without a bearer token: both are reachable only from the host and the compose network.

*Views.*
- <a id="DSH-018"></a>**DSH-018** — The dashboard ships four views: the signals dashboard with ticker search (`/`), the watchlist (`/watchlist`), company detail (`/watchlist/[ticker]`) and login (`/login`), with a navigation bar offering sign-out on every page but login.

## Verification

| ID | Source | Verified by | Status |
|---|---|---|---|
| DSH-001 | `## 2026-10-08 — Control-surface scoping — CHOICE — Grafana for technical health, dashboard for using the application` | no test asserts the absence of health pages; the four shipped views (DSH-018) hold none | `untested` |
| DSH-002 | `## 2026-10-08 — Control-surface scoping — CHOICE — dashboard runs in the stack behind its own server layer`; archived `specs/done/dashboard-foundation.md` [`services/dashboard/README.md`] | `services/dashboard/src/__tests__/api-client.test.ts::test_components_call_only_same_origin_api_paths`, `services/dashboard/src/__tests__/bff.test.ts::test_bff_forwards_get_to_core_hub_using_server_side_url` | `tested` |
| DSH-003 | `## 2026-10-09 — Dashboard foundation — CHOICE — login endpoint, write-token failure mode, path layout` (items 1, 4 and 5); archived `specs/done/dashboard-foundation.md` [`services/dashboard/README.md`] | `services/dashboard/src/__tests__/hash-password.test.ts::test_prints_a_single_quoted_env_line_whose_hash_matches_the_password`, `services/dashboard/src/__tests__/hash-password.test.ts::test_empty_password_is_refused`, `services/dashboard/src/__tests__/auth.test.ts::test_wrong_password_returns_401_and_sets_no_cookie`, `services/dashboard/src/__tests__/LoginForm.test.tsx::test_wrong_credentials_show_the_error` | `tested` |
| DSH-004 | `## 2026-10-09 — Dashboard foundation — CHOICE — login endpoint, write-token failure mode, path layout` (items 1 and 4); archived `specs/done/dashboard-foundation.md` [`services/dashboard/README.md`] | `services/dashboard/src/__tests__/auth.test.ts::test_correct_credentials_set_httponly_samesite_strict_cookie`, `services/dashboard/src/__tests__/auth.test.ts::test_tampered_session_cookie_is_rejected`, `services/dashboard/src/__tests__/auth.test.ts::test_expired_session_is_rejected`, `services/dashboard/src/__tests__/auth.test.ts::test_activity_extends_the_idle_expiry`, `services/dashboard/src/__tests__/auth.test.ts::test_session_ends_when_the_configured_username_changes` | `tested` |
| DSH-005 | `## 2026-10-09 — Dashboard foundation — CHOICE — login endpoint, write-token failure mode, path layout` (item 1); archived `specs/done/dashboard-foundation.md` [`services/dashboard/README.md`] | `services/dashboard/src/__tests__/auth.test.ts::test_health_route_is_reachable_without_session`, `services/dashboard/src/__tests__/auth.test.ts::test_login_page_is_reachable_without_session`, `services/dashboard/src/__tests__/auth.test.ts::test_logout_clears_the_session_cookie`, `services/dashboard/src/__tests__/NavBar.test.tsx::test_sign_out_ends_the_session_and_goes_to_login` | `tested` |
| DSH-006 | archived `specs/done/dashboard-foundation.md` [`services/dashboard/README.md`] | `services/dashboard/src/__tests__/auth.test.ts::test_request_without_session_is_redirected_to_login`, `services/dashboard/src/__tests__/auth.test.ts::test_api_request_without_session_returns_401`, `services/dashboard/src/__tests__/LoginForm.test.tsx::test_sign_in_posts_credentials_and_returns_to_the_requested_page`, `services/dashboard/src/__tests__/LoginForm.test.tsx::test_sign_in_ignores_a_next_target_on_another_origin` | `tested` |
| DSH-007 | `## 2026-10-09 — Dashboard foundation — CHOICE — login endpoint, write-token failure mode, path layout` (item 2); archived `specs/done/dashboard-foundation.md` [`services/dashboard/README.md`] | `services/dashboard/src/__tests__/bff.test.ts::test_bff_forwards_get_to_core_hub_using_server_side_url`, `services/dashboard/src/__tests__/bff.test.ts::test_bff_rejects_unknown_service_without_calling_upstream` | `tested` |
| DSH-008 | archived `specs/done/dashboard-foundation.md` [`services/dashboard/README.md`] | `services/dashboard/src/__tests__/bff.test.ts::test_bff_adds_write_token_on_non_get_requests_only` asserts that neither header reaches the upstream | `tested` |
| DSH-009 | `## 2026-10-09 — Dashboard foundation — CHOICE — login endpoint, write-token failure mode, path layout` (item 3: GET and HEAD need no token); archived `specs/done/dashboard-foundation.md` [`services/dashboard/README.md`; the core-hub side is `docs/core-hub/http-api.md`] | `services/dashboard/src/__tests__/bff.test.ts::test_bff_adds_write_token_on_non_get_requests_only` | `tested` |
| DSH-010 | archived `specs/done/dashboard-foundation.md` [`services/dashboard/README.md`] | `services/dashboard/src/__tests__/bff.test.ts::test_bff_normalises_upstream_error_into_error_shape_with_upstream_status`, `services/dashboard/src/__tests__/bff.test.ts::test_bff_returns_502_with_error_shape_when_upstream_is_unreachable` | `tested` |
| DSH-011 | archived `specs/done/dashboard-foundation.md` [`services/dashboard/README.md`] | `services/dashboard/src/__tests__/bff.test.ts::test_bff_wraps_list_responses_into_items_and_next_cursor`, `services/dashboard/src/__tests__/bff.test.ts::test_bff_passes_no_content_through` | `tested` |
| DSH-012 | `## 2026-10-09 — Dashboard foundation — CHOICE — login endpoint, write-token failure mode, path layout` (item 2: actuator endpoints stay out of reach) [`services/dashboard/src/lib/bff.ts`] | path segments are joined with `encodeURIComponent`, which leaves `.` and `..` segments as they are; no test sends a dot segment | `untested` |
| DSH-013 | archived `specs/done/dashboard-foundation.md` (Constraints; the `NEXT_PUBLIC_API_URL` rule of archived `specs/done/dashboard.md` is history) [`services/dashboard/README.md`] | `services/dashboard/src/__tests__/bundle-secrets.test.ts::test_no_server_secret_appears_in_client_bundle`, run in CI as `npm run test:bundle` after the build | `tested` |
| DSH-014 | archived `specs/done/dashboard-foundation.md` [`services/dashboard/README.md`] | `services/dashboard/src/__tests__/api-client.test.ts::test_components_call_only_same_origin_api_paths`, `services/dashboard/src/__tests__/api-client.test.ts::test_client_raises_the_bff_error_message` | `tested` |
| DSH-015 | `## 2026-10-23 — Living docs — PENDING — strategy-and-dashboard ratification batch` [`services/dashboard/src/lib/bff.ts`]: `UPSTREAM_TIMEOUT_MS`; no approved source sets an upstream timeout | — | `pending-decision` |
| DSH-016 | `## 2026-10-23 — Living docs — PENDING — strategy-and-dashboard ratification batch` [`lib/credentials.ts`]: no approved source states the timing rule | — | `pending-decision` |
| DSH-017 | `## 2026-10-23 — Living docs — PENDING — strategy-and-dashboard ratification batch`; archived `specs/done/dashboard-foundation.md` (Out of scope) [`services/dashboard/README.md`, `services/dashboard/src/lib/bff.ts`] | — | `pending-decision` |
| DSH-018 | archived `specs/done/dashboard.md`, `specs/done/watchlist-ui.md`, `specs/done/dashboard-foundation.md` | `services/dashboard/src/__tests__/SignalsDashboard.test.tsx::test_direct_signals_table_renders_title_source_confidence_date_from_fixture`, `services/dashboard/src/__tests__/Watchlist.test.tsx::test_watchlist_page_renders_existing_entries`, `services/dashboard/src/__tests__/CompanyDetail.test.tsx::test_company_detail_lists_direct_signals`, `services/dashboard/src/__tests__/NavBar.test.tsx::test_login_page_shows_no_navigation` | `tested` |

## Known traps

- A bcrypt hash contains `$`. In `.env`, `DASHBOARD_PASSWORD_HASH` must be single-quoted, or compose reads `$2b` and `$12` as variables and passes a mangled hash; in Next's `.env.local` each `$` is written `\$`. The hash script prints the quoted line. (Moved from root `CLAUDE.md`.)
- Next 16 renamed middleware to `proxy`: `src/proxy.ts` exporting `proxy` runs on the Node runtime and reads `process.env` per request, and a `middleware.ts` is deprecated. `next lint` is gone; lint runs `eslint .` with the flat config. (Moved from root `CLAUDE.md`.)
- Route handlers do not re-check the session; only `src/proxy.ts` does (DSH-006). A handler test that calls the handler directly bypasses the proxy and proves nothing about authorization.

## Retired requirements

None.
