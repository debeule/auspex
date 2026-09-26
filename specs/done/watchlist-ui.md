# Watchlist UI

**Status:** done
**Branch:** `feature/watchlist-ui`

---

## Context

The dashboard has a single search box (ticker → one-off query). There is no persistent watchlist view, no way to manage which stocks to monitor, and no per-company detail page. This spec adds two new pages to the Next.js 15 App Router using the endpoints from the watchlist-backend spec.

The watchlist-backend spec must be completed before the definition-of-done manual smoke test can run. Component tests mock the API and can pass without the backend running.

## What this builds

### `/watchlist` — Watchlist management page

Two sections on a single page:

**Add ticker flow (3 steps, inline):**
1. Text input + "Look up" button. Validates format client-side (`^[A-Z][A-Z0-9.\-]{0,9}$`) before sending.
2. On look-up: calls `GET /api/v1/watchlist/preview?ticker={ticker}`. Shows a preview card with: company name (editable text field if null — SEC lookup failed), detected gene targets split into two groups ("From your existing signals — N total" / "ClinicalTrials programs"). Each gene target is a toggleable chip, pre-selected. User can deselect unwanted ones and type-in additional manual entries.
3. "Add to watchlist" button posts `POST /api/v1/watchlist {ticker, company_name, gene_targets: [...]}`. On success: preview card closes, ticker appears in the watchlist grid.

If the look-up returns 409 (already watching), show "Already watching {ticker}" inline — no separate error page.

**Current watchlist grid:**
Cards, one per watched ticker, showing: ticker symbol (large), company name, gene target count, last signal date. Clicking anywhere on the card navigates to `/watchlist/{ticker}`. Each card has a remove button (trash icon). Clicking remove shows a confirmation: "Remove {TICKER} and its {N} gene targets from the watchlist? Historical signals are preserved." Confirmed click sends `DELETE /api/v1/watchlist/{ticker}`.

### `/watchlist/[ticker]` — Company detail page

Five sections:

1. **Header**: ticker, company name, `external_id`-based link to EDGAR company page (`https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={company_name}&type=8-K`). Back link to `/watchlist`.

2. **Gene targets**: horizontal chip row. Each chip shows gene target name and source badge (graph = blue, clinicaltrials = teal, manual = grey). "＋ Add" opens an inline text input → `PATCH` on Enter. The × on each chip removes it via `PATCH {remove: [name]}`. Changes optimistically update the UI before the API call completes.

3. **Stats bar**: four tiles — Total signals, Total corroborations, Most active gene target, Last signal. Derived from the `stats` block of `GET /api/v1/watchlist/{ticker}/summary`.

4. **Corroborations**: sorted by `corroborated_at` descending. Each row: entity key, source type badges, date. Clicking a row expands an inline detail showing the participant signal titles and published dates. If zero corroborations: "No corroborations yet for these gene targets. More signals needed."

5. **Direct signals**: table — title (links to `source_url`), source type badge, published date, confidence score bar. Reuses `DirectSignalsTable.tsx` component.

### Navigation

Add a top-level nav bar to `layout.tsx` (App Router root layout): two links — "Signals" (existing `/`) and "Watchlist" (`/watchlist`). Active link underlined. The existing `SignalsDashboard.tsx` home page is unchanged.

## Out of scope

Price chart (requires new backend endpoint to read MinIO price Parquet — separate spec). In-app notification feed. Bulk edit of gene targets across multiple watchlist entries. The home page search box is not replaced.

## Constraints

- `NEXT_PUBLIC_API_URL` is the only backend URL. No new env var.
- Vitest + RTL tests. All API calls mocked with `vi.fn()` (or msw if already used in the project). Sockets disabled.
- No `useEffect` poll — preview is triggered only on explicit look-up click.
- Removal confirmation is a blocking UI step — `DELETE` must never be called without user confirmation.
- Gene target chips use optimistic updates. If the `PATCH` fails, roll back the chip state and show an inline error.

## Required tests

Component tests in `services/dashboard/src/`, 8 tests:

- `test_watchlist_page_renders_existing_entries` — mock `GET /api/v1/watchlist` returning two entries; both ticker symbols visible
- `test_lookup_calls_preview_and_renders_card` — type "SRPT", click Look up; mocked preview returns; company name and gene target chips rendered
- `test_company_name_editable_when_null` — preview returns `company_name: null`; text field rendered and editable
- `test_confirm_add_posts_correct_body` — select two gene targets, click Add; verify POST called with `{ticker, company_name, gene_targets}` matching selection
- `test_remove_requires_confirmation` — click trash icon; confirmation dialog appears; DELETE not yet called; cancel → no DELETE; confirm → DELETE called
- `test_company_detail_renders_gene_target_chips` — mock summary; gene targets rendered as chips with correct source badges
- `test_company_detail_renders_corroboration_rows` — corroboration list present, sorted newest first
- `test_gene_target_chip_remove_sends_patch` — click × on "DMD" chip; `PATCH /api/v1/watchlist/SRPT/gene-targets` called with `{remove: ["DMD"]}`

## Definition of done

```bash
cd services/dashboard && npm run test
```

Expected: prior passing tests + 8 new tests passed.

Then: manual smoke test against a running full stack — add SRPT, confirm company name and gene targets resolve, navigate to detail page, verify signals and corroborations render.

## Notes

The company name editable-when-null UX handles the case where a small or recently-listed biotech ticker is not in the SEC JSON cache. The user types the company name manually and the POST accepts it — core-hub validates only that it is non-empty.

The gene target chip source badge distinguishes how the target was discovered. Over time, as the system accumulates signals, `source: 'graph'` targets gain signal counts. This gives the user a natural way to see which gene targets are actively generating signals vs. which were suggested by ClinicalTrials but have no signals yet.
