# Dashboard

**Status:** done
**Blocked by:** —
**Branch:** `feature/dashboard`

---

## Context

`GET /api/v1/signals/{ticker}` is live in `core-hub` and returns a `TickerSignalsResponse` with two lists:

- `directSignals` — signals whose extracted company mentions include that ticker. Each carries: `eventId`, `sourceType`, `title`, `summary`, `confidenceScore` (0.0–1.0), `publishedAt`.
- `corroboratedSignals` — live (non-superseded) corroboration records that include at least one of those signals. Each carries: `entityKey` (e.g. `"BCL11A:GeneTarget"`), `sourceTypes`, `corroboratedAt`, `confidence`, `participantEventIds`.

Nothing in `services/` has a frontend. The new app lives at `services/dashboard/`.

Node version is resolved as part of this spec (VERSIONS.md deferred it to Phase 5). Node 22 LTS is current.

## What this builds

A Next.js 15 (App Router, TypeScript, Tailwind CSS) single-page dashboard at `services/dashboard/` where a user enters a ticker symbol, the app calls `GET /api/v1/signals/{ticker}` on `core-hub`, and the result is displayed as:

- A table of direct signals: title, source type, confidence (as a percentage), published date.
- A corroborated signals panel: entity key, joining source types, corroboration confidence, corroborated date.
- An empty state when both lists are empty.
- An error message when the API is unreachable or returns non-2xx.

## Out of scope

Auth. Real-time push updates. Any new `core-hub` endpoint (if the API needs extending, that is a separate `core-hub` PR first). Entity graph force-directed visualization. Mobile layout. Pagination.

## Constraints

- All data through the existing REST API. No direct DB or Neo4j access from the frontend.
- Ticker input enforces the same allowlist as the backend: `^[A-Z][A-Z0-9.\-]{0,9}$`. Validated client-side before fetch; backend will also reject it, but the UI must give immediate feedback without a round trip.
- `NEXT_PUBLIC_API_URL` is the only API base URL source — never hardcoded.
- Confidence scores are displayed as percentages (multiply by 100, round to one decimal: `0.875` → `87.5%`).

## Required tests

Component/unit tests (Vitest + React Testing Library), no live server:

- `test_direct_signals_table_renders_title_source_confidence_date_from_fixture` — given a fixture response with one direct signal, the rendered output contains the title text, source type, a percentage-formatted confidence value, and the formatted published date.
- `test_corroborated_panel_renders_entity_key_and_source_types_from_fixture` — given a fixture response with one corroborated signal, the rendered output contains the entity key string and each source type in the `sourceTypes` list.
- `test_empty_state_renders_when_both_signal_lists_are_empty` — given a response with `directSignals: []` and `corroboratedSignals: []`, the output contains an empty-state message and zero table rows.
- `test_api_error_renders_error_message_not_blank_page` — when the fetch rejects (network error), the component renders a human-readable error message. The error does not propagate as an unhandled React render error.
- `test_ticker_input_rejects_lowercase_and_invalid_characters_before_fetch` — submitting a lowercase ticker string (`"beam"`) or one containing spaces (`"BEA M"`) shows a validation error and does not invoke the API fetch.

## Definition of done

```bash
cd services/dashboard && npm test -- --run
```

All 5 tests pass, zero skipped.

```bash
cd services/dashboard && npm run build
```

Build succeeds with no TypeScript errors and no Next.js build errors.

## Notes

- `package.json` engines: `{"node": "22.x"}`. Add `.nvmrc` containing `22`.
- Dev dependencies: `vitest`, `@vitest/coverage-v8`, `@testing-library/react`, `@testing-library/user-event`, `jsdom`. Configure Vitest with `environment: 'jsdom'` and a `setupFiles` that imports `@testing-library/jest-dom/vitest`.
- The API base URL in development is `http://localhost:8080`; set it in `.env.local` (gitignored). `.env.local.example` is committed with the placeholder.
- The ticker allowlist regex must be extracted into a shared utility so both the form validation and any server-side API route proxy use the same pattern.
