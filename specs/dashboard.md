# Dashboard

**Status:** draft
**Blocked by:** —
**Branch:** `feature/dashboard`

---

## Context

The REST API (`GET /api/v1/signals/{ticker}`) is live in `core-hub`. This spec adds a frontend. Nothing in `services/` currently has a frontend.

## What this builds

A Next.js app that visualises the entity graph and recent corroborated signals using the existing REST API. Does not add a parallel API — if a data gap appears, extend `SignalController` in `core-hub`.

## Out of scope

Auth (separate conditional spec). Real-time push updates. This is a polling frontend over the existing REST API.

## Constraints

- All data through the existing REST API — no direct DB queries from the frontend.
- If `SignalController` needs extension, that change belongs in `core-hub` under the same invariants (parameterized queries, write-order, etc.).

## Required tests

- `test_graph_renders_from_api_fixture`
- `test_empty_state_renders`
- `test_api_error_renders_error_state_not_blank_page`

## Definition of done

Suite passes and the dashboard renders live data from the running API.

## Notes

Needs scoping before `ready`: what data does the graph show? What time range? What does the corroborated signal list look like? Tech stack: Next.js is noted in the original plan but confirm Node version at that point (currently deferred to Phase 5 in `VERSIONS.md`).
