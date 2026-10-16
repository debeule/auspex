# Living docs: strategy layer and dashboard

**Status:** blocked
**Blocked by:**
1. `specs/docs-check-tooling.md`. It provides `python3 -m tools.docs_check`, `docs-check.toml` and the integration branch `feature/living-docs-integration`.
2. `specs/living-docs-system-and-contracts.md`. It provides:
   - `docs/README.md`;
   - `docs/system/invariants.md` (INV-1…15);
   - `docs/system/contracts.md` (the CON IDs for the corroborated event).
3. `specs/living-docs-core-hub.md`. It provides `docs/core-hub/http-api.md`.
   - The dashboard doc links the write-token and no-CORS requirements (HUB) there and does not restate them.
   - The four dashboard view specs edited here cite HUB and COR IDs.
4. `specs/living-docs-research.md`. It provides `docs/research/simulation.md`, `panels.md` and `evaluation-protocol.md`. The strategy docs link to:
   - the market simulation;
   - the catalyst and short-interest panels;
   - the trial ledger;
   - the protocol ceilings;
   - the read-only research config.
5. Owner answers. Each is cited as its CHOICE once appended, and as the PENDING heading until then.
   - `## 2026-10-15 — Living docs — PENDING — as-of reads hide or raise`. This blocks the as-of requirement in `contract.md`. The default is that hiding is the approved behaviour and the `AsOfContext` docstring is stale.
   - `## 2026-10-15 — Living docs — PENDING — can a DECISIONS entry narrow an invariant`. This does not block: the default records the runtime's missing DLT as `divergent` under INV-11.
   - `## 2026-10-15 — Living docs — PENDING — processing time in as-of decisions`. This does not block.
   - `## 2026-10-15 — Living docs — PENDING — defects found while scoping`. This does not block.

**Branch:** `feature/living-docs-strategy-and-dashboard` (from `feature/living-docs-integration`; PR into it)

**Docs impact:**
- Creates `docs/strategy/contract.md`, `runtime.md`, `risk.md` and `decision-trace.md` (namespace STR), and `docs/dashboard.md` (namespace DSH).
- Modifies 7 active specs: adds `Docs impact`, replaces restated requirements with IDs, fixes stale spec paths and adds missing required sections.
- Appends one PENDING ratification-batch heading to `DECISIONS.md`.
- Fills, in `specs/living-docs-cutover-matrix.md`:
  - the STR and DSH ID cells;
  - the `IDs` cells of the binding Decisions rows that this spec carries.
- Removes `strategy` and `dashboard` from `[rollout] planned_domains` in `docs-check.toml`.
- Moves this spec to `specs/done/` and updates its own `TODO.md` row.
- Changes no README, no code and nothing under `config/`.

---

## Context

**Repository state.** All paths are relative to the repo root at `e51f742` (develop).

**Where the requirements live today.** `docs/requirements.md` has no strategy or dashboard section; its headings stop at §14. Today the rules live in five places:
- **Archived specs:**
  - `specs/done/strategy-framework.md`;
  - `strategy-runtime.md`;
  - `portfolio-and-risk.md`;
  - `decision-trace.md`;
  - `strategy-metrics.md`;
  - `dashboard-foundation.md`;
  - the superseded `NEXT_PUBLIC_API_URL` sections of `dashboard.md` and `watchlist-ui.md`.
- **`DECISIONS.md` `CHOICE` entries.** The Decisions table of `specs/living-docs-cutover-matrix.md` classifies each one as binding or history. Its section "Research, strategy and dashboard" maps every strategy and dashboard statement to a target.
- **`services/strategy/README.md`** (96 lines): the most accurate description of the current state.
- **`services/dashboard/README.md`** (43 lines).
- **Config authorities:**
  - `config/strategies/registry.yaml`: five strategies, all `status: draft`;
  - `config/themes.yaml`: maps only the 8 watched tickers. Its header comment says an unmapped ticker is rejected.

**What runs today.** Under `services/strategy/src/auspex_strategy/`:
- **Contract:** `abc.py` (`Strategy`, `AsOfContext`), `models.py`, `registry.py`, and the contexts in `runtime/context.py`.
- **Runtime:** `runtime/replay.py`, `runtime/streaming.py` and `runtime/main.py`. The `strategy-runtime` compose service is in the `app` profile.
- **Books and broker:** `runtime/book.py`, `runtime/broker.py`.
- **Risk:** `risk/` (manager, review, limits, flow, kill switch, catalysts, shorts, sizing, themes).
- **Trace:** `trace/`.
- **Metrics:** `metrics/`, served on the runtime HTTP server (`runtime/http.py`).

The dashboard (`services/dashboard/src/`) consists of:
- `proxy.ts`: the session gate;
- `lib/session.ts` and `lib/credentials.ts`;
- `lib/bff.ts`, with the upstreams at `:13-15`;
- `lib/api.ts`;
- the route handlers `app/api/[service]/[...path]/route.ts`, `app/api/auth/{login,logout}` and `app/api/health`;
- the pages `/`, `/watchlist`, `/watchlist/[ticker]` and `/login`.

**Code facts this spec depends on.** Each was verified at `e51f742`. The writer re-reads each one before writing its row. Facts labelled E F3, E F4 or E F6 are items of `## 2026-10-15 — Living docs — PENDING — defects found while scoping`.

| Fact | Code | Use |
|---|---|---|
| **As-of contract.** The `AsOfContext` docstring says that reads past as-of raise `AsOfViolationError`. The production `_RecordContext` drops unknown records at construction (`if r.corroborated_at + self._delay <= as_of`), so the raise in `corroborations()` can never fire. The raise tests use `StubAsOfContext` (`testing.py`). `test_backtest_context_hides_records_not_yet_known` asserts the hiding. | `abc.py:18-24`; `runtime/context.py:52`, `:70-72`; `tests/unit/test_runtime_components.py:330`; `test_strategy_framework.py:118,133` | as-of decision |
| **Risk and tracer not wired (E F3).** The streaming runtime is built with `PassThroughRiskManager`. No production code constructs `PortfolioRiskReview` or `DecisionTracer`; only `trace/replay.py` does. Only `KillSwitch` is wired, and exit intents from `risk/manager.py` are never executed. | `runtime/main.py:150,160`; grep of `src/` | divergent |
| **No input-health provider (E F4).** The runtime polls `/api/v1/health/inputs` and counts no answer as unhealthy, but core-hub `src/main` has no such route. The compose comment says core-hub "serves the per-input health the runtime polls". | `runtime/health.py:17`; grep of `services/core-hub/src/main`; `docker/docker-compose.yml:537` | divergent |
| **Restart idempotency (E F6).** The offset is checkpointed after `process()`, so a crash between `broker.submit` and `checkpoint.save` re-processes the event. `VirtualBook.place_order` mints `uuid4` order ids and does not dedupe on `intent_id`. Live history and the daily-loss state live only in memory. | `runtime/streaming.py:189-208`; `runtime/book.py:137-151`; `risk/flow.py:22,43` | divergent (INV-10) |
| **No runtime DLT.** An unreadable corroborated payload is logged, counted (`rejected_events`) and skipped, with no DLT. `## 2026-10-10 — Strategy runtime — CHOICE — state placement, timing and the pass-through stub`, item 5, accepts this. | `runtime/streaming.py:200-207` | divergent (INV-11) |
| **No ticker or source types on live records.** `ticker_for=lambda entity_key: None`. | `runtime/main.py:151-152` | divergent |
| **Versions not checked in production.** `load_registry` passes no `versions_dir`, so a code change without a version bump goes undetected in production. With `versions_dir` set, `_check_version` writes `versions/<name>/<version>.json`. | `runtime/main.py:93-97`; `registry.py:134-142` | divergent; read-only-config trap |
| **Live statuses fill on paper.** `live-confirm` and `live-auto` map to virtual books filled by `PaperBroker`. `BookMode.LIVE` is unused. | `runtime/slots.py:14-18`; `runtime/book.py:30-32` | ratification |
| **Signals differ between replay and streaming.** Replay passes signals, and streaming passes none. Signals are filtered by `published_at <= as_of`, with no known-at delay. | `runtime/replay.py:93`; `runtime/context.py:53` | ratification |
| **Strategy API unreachable from the dashboard.** The runtime HTTP server binds `0.0.0.0`, and compose publishes it on `127.0.0.1:8003`. The BFF has no strategy upstream. | `runtime/http.py:91`; `services/dashboard/src/lib/bff.ts:13-15` | note |
| **Possible path traversal.** BFF paths are joined with `encodeURIComponent` under `basePath`, and no test covers dot segments. | `bff.ts:48` | untested |
| **Handlers trust the proxy.** Route handlers do not re-check the session; only `proxy.ts` does. | `src/proxy.ts`; `app/api/[service]/[...path]/route.ts` | trap |
| **`ExitOnSignal` closes nothing.** A position opened with `ExitOnSignal` never closes. | `runtime/broker.py:97-108` (only `FixedDays` and `StopLossPct` close) | trap |

**What does not exist:**
- `docs/strategy/`, `docs/dashboard.md` and `tools/docs_check/`;
- forward paper trading (`PaperLedger`, heartbeats, close-out) and live trading. Their specs stay in `specs/`, and no living doc is created for them.

**Required sections missing in two specs this spec edits.** At `e51f742`, `specs/live-trading.md` has `## What this builds (to be scoped)`. `specs/research-results-view.md` has `## What this builds (to be confirmed at scoping)` and `## Required tests (provisional; confirm at scoping)`. Check E matches the section names exactly, so these count as missing.

## What this builds

When this spec merges into the integration branch, every approved strategy-layer and dashboard rule has one owner file and an ID. Every known gap between a rule and the runtime is visible as a `divergent` row with its decision.

**Template** (`specs/living-docs-cutover-design.md` §5.1). Each of the five docs has:
- **A header line:** `Domain: STR` (or `DSH`) `· Code: <paths> · Last reviewed against: develop @ <rollout base SHA>`.
- **Required H2s:** `Scope`, `Requirements`, `Verification` and `Retired requirements` (the last one empty).
- **Optional H2s,** where they have content: `Machine-readable authorities`, `Known traps` and `Rationale`.
- **Each requirement:** `<a id="STR-NNN"></a>**STR-NNN**`, followed by one present-tense, testable statement.
- **The verification table:** the first table under `## Verification`, with columns `ID | Source | Verified by | Status`. Status is one of `tested`, `enforced`, `untested`, `divergent` or `pending-decision`.
  - A `tested` row cites `path::name` of a test read in the code. For TypeScript, `name` is the literal string in `it('…')`.
  - A `divergent` or `pending-decision` row cites an existing `DECISIONS.md` heading.
  - A `Source` that rests on a decision contains that heading's text verbatim, after `## `.

**Writing rules:**
- Allocate IDs in file order with `python3 -m tools.docs_check --next STR` and `--next DSH`.
- Name values by file and key; never copy them.
- The lists below give the content each file must cover. The wording is the writer's, checked against the code.

### 1. `docs/strategy/contract.md` (STR)

Code: `abc.py`, `models.py`, `registry.py`, `runtime/context.py`, `strategies/`. Machine authorities: `config/strategies/registry.yaml` and the hypothesis files (link EVA).

- **The `Strategy` ABC.** It declares `name`, `version`, `hypothesis_id`, `subscriptions`, `declared_inputs` and `parameters`. `decide()` is a function of its `AsOfContext` alone.
- **Strategy parameters live only in the registered hypothesis file.**
  - Source: `## 2026-10-10 — Single-source cleanup — CHOICE — one version of each pre-rollout artifact`.
  - Test: `test_strategy_parameter_files_do_not_redeclare_hypothesis_fields`.
- **`AsOfContext` is the only data channel.** A corroboration is known at `corroborated_at` plus the strategy's registered known-at delay (`## 2026-10-10 — Strategy runtime — CHOICE — state placement, timing and the pass-through stub`, item 2).
- **As-of reads.** A record not yet known at `as_of` is not returned: production contexts hide it. A context never returns a record past its known-at boundary.
  - Status `tested` (`services/strategy/tests/unit/test_runtime_components.py::test_backtest_context_hides_records_not_yet_known`).
  - Source: the CHOICE answering "as-of reads hide or raise" (the PENDING heading until it exists).
  - The `abc.py:18-24` docstring still promises a raise, so it is stale. It goes under Known traps, and a follow-up fix spec corrects it, because this rollout changes no code.
  - If the owner chooses "raise" instead, this requirement says "raises", with status `divergent` citing that CHOICE.
- **Prices.** A price read is allowed only for sessions strictly before `as_of.date()`. Anything else raises `PriceLookAheadError`. Test: `test_backtest_context_refuses_a_close_that_is_not_final`.
- **No processing time.** No context method exposes `ingested_at` or `extracted_at`.
  - Source: `## 2026-09-20 — Strategy layer session 2 — CHOICE — Strategies never see ingested_at or extracted_at; InputHealthMonitor handles model downtime`.
  - This STR requirement carries the rule. The sixteenth invariant does not exist during this spec: nobody writes it before the owner's CHOICE on "processing time in as-of decisions", and if that CHOICE adopts it, the cutover writes it (step 3).
  - Link the RES aligner rule; do not restate it.
- **Signals in replay and streaming.** Replay and streaming expose the same signals to a strategy. Ratification batch, status `pending-decision` (`runtime/replay.py:93`; `runtime/context.py:53`).
- **Registry.** Source: archived `strategy-framework`; its tests are in `test_strategy_framework.py`.
  - Every strategy names a registered hypothesis.
  - There is one strategy per tradeable hypothesis.
  - Adding a strategy needs only its module and a registry entry; the contract suite discovers it.
  - A `retired` strategy raises in `decide()` and stays listed.
- **Versioning.** A strategy is versioned on its code hash and parameter hash. A change without a version bump is refused.
  - `divergent` in production (`runtime/main.py:93-97`), citing the defects-found PENDING heading.
  - Known trap: the check writes under `config/strategies/`. The read-only research config rule (EVA, linked) forbids that at runtime, and the compose mount is `:ro`.
- **Lifecycle order.** `draft` < `research` < `paper` < `live-confirm` < `live-auto`, plus `retired`.
- **`live-confirm` and `live-auto` are reserved.** No broker exists, so a strategy at either status trades only virtual books. Ratification batch (`runtime/slots.py:14-18`). Live trading stays in `specs/live-trading.md`.
- **`TradeIntent` fields and units.** `StopLossPct` is in percent. Source: `## 2026-10-11 — Portfolio and risk — CHOICE — catalyst and short-interest sources, units and check order`, item 6.

### 2. `docs/strategy/runtime.md` (STR)

Code: `runtime/`, `metrics/`, `__main__.py`. Values are in `.env.example` and are named only.

**Service boundaries.**
- **A separate service.** It uses `auspex_backtesting`'s market simulation as a path dependency and never copies it (link `docs/research/simulation.md`). Source: ``## 2026-09-20 — Strategy layer session 2 — CHOICE — New `services/strategy/` service (not extending backtesting)``.
- **State only in MinIO.** All runtime state is in the `auspex-strategy` bucket under `strategy/`, at the key layout in the README table. The runtime writes no Postgres or Neo4j (applies INV-2). Sources:
  - `## 2026-09-20 — Strategy layer session 2 — CHOICE — MinIO for virtual books and traces; strategy service serves metrics API` (the Flask detail is history);
  - runtime CHOICE item 1.

**Replay and streaming.**
- **Replay:**
  - runs `research`-or-above strategies;
  - sends the `paper`-or-above intents of each event to risk together;
  - trades only `backtest` books, never a forward book;
  - runs `decide()` inline;
  - is deterministic, including `intent_id` (`test_backtest_replay_is_deterministic`).
- **Streaming.** Sources: `## 2026-09-20 — Strategy layer session 2 — CHOICE — Event-driven Kafka consumer for the strategy runtime`; runtime CHOICE item 5. The topic and wire shape are linked to CON, not restated.
  - It consumes the corroborated topic in its own consumer group and runs `paper`-or-above strategies.
  - It publishes no topic.
  - It never commits Kafka offsets: the MinIO checkpoint saved after each event is the resume position.

**Divergent rows.**
- **No runtime DLT.** An unreadable payload never blocks the partition and never disappears without a record. Status `divergent` against INV-11.
  - The runtime logs, counts and skips the payload, with no dead-letter record (`runtime/streaming.py:200-207`).
  - Cite the runtime CHOICE (item 5) and `## 2026-10-15 — Living docs — PENDING — can a DECISIONS entry narrow an invariant`.
  - A `DECISIONS.md` entry cannot narrow INV-11. Either an INV-11 exception in `docs/system/invariants.md` or a fix spec closes it.
  - DLT naming and headers are CON's; link them.
- **Restart idempotency.** Re-processing an event after a restart books no second order for the same `intent_id`. The live history and the daily-loss state survive a restart.
  - Status `divergent`. Applies INV-10.
  - Cite `## 2026-10-10 — Strategy runtime — FLAG — the live data channel is not fully served by core-hub yet` and the defects-found PENDING heading, item E F6.
- **Input health.** A strategy that declares an input is paused while that input is unhealthy, and resumes when it recovers.
  - No answer counts as unhealthy.
  - Pauses are recorded.
  - Events skipped while paused are not counted as seen.
  - `tested` for the client side (`test_stale_input_source_pauses_strategy`, `test_recovered_input_ends_the_pause`).
  - A second row states that the provider exists, with status `divergent`. Cite the 2026-10-10 Strategy runtime FLAG and the defects-found heading, item E F4. The provider contract is HUB's: link the HUB ID in `docs/core-hub/http-api.md`, or the file if no ID exists.
- **Live records.** A live corroboration record carries its ticker and source types. Status `divergent` (`runtime/main.py:151-152`), citing the same FLAG.

**Execution.**
- **Isolation** (runtime CHOICE item 4).
  - A crash, a timeout or an invalid intent counts against that strategy and never reaches another.
  - The timeout applies in streaming only.
  - A timed-out call keeps running in its thread, and its result is discarded.
- **Fills** (runtime CHOICE item 3).
  - Entry is at the open of the first NYSE session after the `as_of` date.
  - A live order waits for its entry bar.
  - Exits follow `FixedDays` or `StopLossPct` through `FillModel`.
  - Costs and the EUR conversion equal the market simulation's (`test_virtual_book_pnl_matches_market_simulation`).
- **Book rows are append-only.** Each row carries the `strategy_version` of the intent that placed the order. A trade belongs to the version that opened it (`## 2026-10-11 — Strategy metrics — CHOICE — where the spec left the metrics open`, item 1).
- **Bookkeeping.**
  - Overlapping intents across strategies are flagged.
  - Corroboration-to-intent latency is recorded per intent. A startup warning is raised when the median exceeds the known-at delay.
  - Funnel counts are kept per version and mode.
- **Risk review.**
  - All of an event's tradable intents go to one risk review.
  - A killed strategy's intents are dropped before risk.
  - The review itself belongs to `risk.md`. This file links it, and the runtime-wiring row is there.

**Metrics.** Sources: strategy-metrics CHOICE items 1–8; `## 2026-09-20 — Strategy layer session 2 — CHOICE — Minimum 20 trades before metrics and Kelly sizing`.
- Metrics are computed on request, never stored.
- Each figure covers one strategy version in one mode.
- Every group carries its `n`.
- Below `MIN_TRADES_FOR_METRICS`, a group reports `insufficient_data: true` with null statistics.
- The per-trade abnormal return definition links EVA for the model.
- The deflated Sharpe uses per-trade returns and the family trial count, read without the lock (link EVA).
- Each version is compared against the same version's backtest book.
- The correlation matrix.
- A break-even trade counts as a loss.
- The drawdown definition.

**HTTP and CLI.**
- **HTTP surface.** `/health`, `/metrics` and the `/api/v1/metrics/*` route shapes, on the runtime's own port.
  - The routes have no authentication.
  - Host exposure is localhost only: link `docs/operations/topology.md`.
  - No dashboard route reaches them yet. Say so in Scope.
- **The kill-switch CLI** runs without Docker.

**Known traps.**
- `ExitOnSignal` positions never close.
- The kill-switch event log assumes a single writer, but the CLI and the runtime both append (`trace/store.py`, read-then-put).
- The memory limit belongs to `docs/operations/topology.md`.

### 3. `docs/strategy/risk.md` (STR)

Code: `risk/`, `runtime/risk.py`. Machine authorities:
- `config/hypotheses/protocol.yaml` `sizing` and `instruments` (link EVA; never copy the values);
- `config/themes.yaml`;
- the risk-limit variables in `.env.example`.

Main sources:
- `## 2026-10-11 — Portfolio and risk — CHOICE — catalyst and short-interest sources, units and check order`, items 1–9;
- `## 2026-10-07 — Pre-registration — CHOICE — sizing ceilings: quarter Kelly, 5% per name, one position per theme, no hold through binary events`.

Requirements:
- **Limits.** Every limit is an `.env` variable. Startup fails, naming the variable, when one is missing or looser than the protocol ceiling (the protocol hash is verified). `MIN_TRADES_FOR_KELLY` may not go below its floor.
- **Units.** `*_PCT` limits on capital are fractions. Borrow fee, short interest and stop are in percent.
- **Check order.** `RiskManager.evaluate` runs these checks:
  1. drawdown;
  2. kill switch;
  3. sizing;
  4. position limits;
  5. binary-event guard;
  6. short guard;
  7. daily loss and turnover.

  The first failure rejects, and every check that ran is recorded.
- **Kelly sizing.**
  - Quarter Kelly shrinks only `p` toward 0.5.
  - Below the minimum number of trades, a fallback size applies.
  - Sizes are capped per name.
  - An intent with no edge is rejected.
- **Themes.**
  - One position per theme across strategies.
  - Themes come from `config/themes.yaml`.
  - An unmapped ticker is rejected as `THEME_UNMAPPED`, never treated as uncorrelated.
  - Sources: the `themes.yaml:3-4` comment and archived `portfolio-and-risk`.
- **Catalyst guard.** The guard reads the point-in-time catalyst panel (link RES).
  - A ticker without a CIK is rejected as `CATALYST_UNKNOWN`.
  - An imprecise period counts by overlap.
  - An exit lands on the last session before the period.
  - Holds through a declared catalyst type are logged.
  - The guard is never waived for shorts.
  - Readouts are unguarded, because they have no source.
- **Shorts.**
  - Shorts are rejected while the protocol disables them.
  - `ShortGuard` reads the short-interest store, using the period published by the day before.
  - With no data, it skips the crowding checks with a warning.
  - The borrow fee is flat.
- **Loss limits and kill switch.**
  - The daily-loss block lasts the rest of the day.
  - Turnover has a ceiling.
  - A drawdown breach turns the global kill switch on.
  - The kill switch is global or per strategy. Open positions keep their exits, and triggers and resets are logged.
- **`RiskDecision`.** Source: `## 2026-10-11 — Decision trace — CHOICE — one document record per participant, deterministic intent ids, risk reviews per event`, item 3.
  - A decision is `APPROVED`, `REJECTED` or `PAUSED`.
  - Kill switch, drawdown and daily loss map to `PAUSED`.
  - `PortfolioRiskReview` counts earlier approvals toward the limits.
- **Runtime wiring.** The streaming runtime reviews every intent through `RiskManager`, and exit intents are executed.
  - Status `divergent`. Cite `## 2026-10-11 — Portfolio and risk — FLAG — the runtime still sizes with the pass-through stub` and the defects-found heading, item E F3.
  - Scope says plainly: the library is implemented and tested, but the runtime enforces only the kill switch.
- **Capital allocation.** Capital across promoted strategies follows an equal risk budget with a correlation cap.
  - Status `divergent`, because it is not implemented.
  - Cite `## 2026-09-20 — Strategy layer session 2 — CHOICE — Equal risk budget per promoted strategy; correlation-aware cap` and the defects-found PENDING heading.
  - The ratification batch asks the owner to confirm it is still intended. If it is not, retire the ID on the owner's word.

**Known traps.**
- `themes.yaml` maps only the 8 watched tickers, so every other universe ticker is `THEME_UNMAPPED`.
- The daily-loss state lives in memory.

### 4. `docs/strategy/decision-trace.md` (STR)

Code: `trace/`. Main sources: the 2026-10-11 Decision trace CHOICE (items 1–4) and archived `decision-trace`.

- **One `TraceRecord` per risk-reviewed intent** of a `paper`-or-above strategy, with:
  - one `DocumentRecord` per participant;
  - the corroboration key `(entity_key, participants_hash)` (`## 2026-09-20 — Strategy layer session 2 — FLAG — Corroboration surrogate key deferred; composite natural key in trace`);
  - the risk checks and outcome, netting and sizing;
  - execution and P&L fields, empty until fills are traced.
- **`extracted_at` is nullable** (`## 2026-09-20 — Strategy layer session 2 — FLAG — extracted_at missing from ResearchSignalEvent (§10.2)`).
- **One validator for every mode.**
  - It names each missing field.
  - An incomplete trace is never appended. So a pass-through decision, or an event without archived documents, cannot be traced.
- **`TraceStore`** is append-only JSONL.
- **Deterministic intent ids:** UUIDv5 over strategy, version, corroboration key, `as_of` and position, with a fixed namespace.
- **Replay.** Replaying a trace reproduces every field except `trace_id`, `approved_at` and `fill_time`.
- **Paper and live tracing.** Paper and live decisions are traced.
  - Status `divergent`, because streaming has no tracer.
  - Cite the Decision trace CHOICE (its Action), the 2026-10-10 Strategy runtime FLAG and the defects-found heading, item E F3.

### 5. `docs/dashboard.md` (DSH)

Code: `services/dashboard/src/`, `scripts/hash-password.mjs`.

**Scope.**
- The dashboard is the application's interface. Technical health is Grafana's: link `docs/operations/observability.md`. Source: `## 2026-10-08 — Control-surface scoping — CHOICE — Grafana for technical health, dashboard for using the application`.
- The write-token and no-CORS requirements are owned by `docs/core-hub/http-api.md`. This file links their HUB IDs and states only the dashboard half: the BFF attaches the token on core-hub writes.

**Requirements.** Each test below is `services/dashboard/src/__tests__/<file>::<name>`.
- **Origin.** The browser calls only the dashboard's origin. Route handlers hold no business logic and touch no datastore. Source: `## 2026-10-08 — Control-surface scoping — CHOICE — dashboard runs in the stack behind its own server layer`.
- **Login.** Single-user login from `.env`, with a bcrypt hash produced by the hash script (`hash-password.test.ts::test_prints_a_single_quoted_env_line_whose_hash_matches_the_password`). Source: `## 2026-10-09 — Dashboard foundation — CHOICE — login endpoint, write-token failure mode, path layout`, items 1, 4 and 5. Sessions:
  - use an HMAC-signed cookie, `HttpOnly` and `SameSite=Strict` (`auth.test.ts::test_correct_credentials_set_httponly_samesite_strict_cookie`);
  - are `Secure` only over HTTPS;
  - expire when idle and are re-issued on each request (`auth.test.ts::test_activity_extends_the_idle_expiry`, `auth.test.ts::test_expired_session_is_rejected`);
  - end when the username changes (`auth.test.ts::test_session_ends_when_the_configured_username_changes`);
  - reject tampered cookies (`auth.test.ts::test_tampered_session_cookie_is_rejected`);
  - reject a wrong password with 401 and no cookie (`auth.test.ts::test_wrong_password_returns_401_and_sets_no_cookie`).
- **Public routes.** Only `/login`, `/api/health` and `POST /api/auth/login` need no session (`auth.test.ts::test_health_route_is_reachable_without_session`, `auth.test.ts::test_login_page_is_reachable_without_session`). Logout clears the cookie (`auth.test.ts::test_logout_clears_the_session_cookie`).
- **Authorization.** `src/proxy.ts` is the only authorization point.
  - Pages redirect to login with `next` (`auth.test.ts::test_request_without_session_is_redirected_to_login`).
  - API routes answer 401 (`auth.test.ts::test_api_request_without_session_returns_401`).
  - A `next` on another origin is ignored (`LoginForm.test.tsx::test_sign_in_ignores_a_next_target_on_another_origin`).
- **BFF.** Source: Dashboard foundation CHOICE item 2.
  - One handler per upstream. core-hub is mounted under its `/api` prefix, so actuator endpoints are out of reach (`bff.test.ts::test_bff_forwards_get_to_core_hub_using_server_side_url`).
  - An unknown service is rejected without an upstream call (`bff.test.ts::test_bff_rejects_unknown_service_without_calling_upstream`).
  - The browser's `cookie` and `authorization` headers are never forwarded.
  - The write token is attached on core-hub non-GET requests (`bff.test.ts::test_bff_adds_write_token_on_non_get_requests_only`), with a link to the HUB ID.
  - Errors use the shape `{error: {code, message, upstream_status}}`. 4xx passes through; 5xx and unreachable upstreams become 502 (`bff.test.ts::test_bff_normalises_upstream_error_into_error_shape_with_upstream_status`, `bff.test.ts::test_bff_returns_502_with_error_shape_when_upstream_is_unreachable`).
  - Lists are wrapped as `{items, next_cursor}` (`bff.test.ts::test_bff_wraps_list_responses_into_items_and_next_cursor`), and 204 passes through (`bff.test.ts::test_bff_passes_no_content_through`).
- **Path containment.** The BFF never forwards a request outside the upstream's base path.
  - Status `untested` (`bff.ts:48`).
  - Source: Dashboard foundation CHOICE item 2 ("so actuator endpoints stay out of reach").
- **Secrets.** No server secret or backend URL reaches the client bundle, and there is no `NEXT_PUBLIC_*` backend setting.
  - Test: `bundle-secrets.test.ts::test_no_server_secret_appears_in_client_bundle`, run in CI as `test:bundle`.
  - Source: archived `dashboard-foundation`, Constraints.
  - The superseded `NEXT_PUBLIC_API_URL` rule of archived `dashboard.md` is history.
- **API client.** Components call the backend only through the typed client, on same-origin paths (`api-client.test.ts::test_components_call_only_same_origin_api_paths`).
- **Research config.** Research config is shown read-only. Link the EVA ID; do not restate it.
- **Ratification batch:**
  - the upstream timeout (`bff.ts:68`);
  - the credential check compares a hash even for an unknown username (`lib/credentials.ts`);
  - scraper and price-service writes are forwarded with no token, under the localhost-only threat model (archived `dashboard-foundation`, Out of scope).
- **Shipped views.** Ticker search, watchlist, company detail and login. This is descriptive; proposed views stay in their specs.

**Known traps.**
- **bcrypt `$` in `.env`:** single-quote the value in `.env`, and write `\$` in `.env.local`.
- **Next 16 renamed middleware to `proxy`,** and `next lint` is gone.
- **Route handlers do not re-check the session.** A handler test that bypasses `proxy.ts` proves nothing about authorization.

### 6. One ratification batch

Append one entry to `DECISIONS.md`: `## <date> — Living docs — PENDING — strategy-and-dashboard ratification batch`. In this spec, `strategy-and-dashboard ratification batch` in a Source cell is shorthand: the doc's verification `Source` cell carries the full citation `` `## <date> — Living docs — PENDING — strategy-and-dashboard ratification batch` `` with the date the entry is appended, as check K requires for `pending-decision` rows. It lists every requirement above marked "ratification batch", and any other requirement whose only source the writer finds to be code or a README. Each is written with Source `strategy-and-dashboard ratification batch` plus the code path, and status `pending-decision`.

**STR:**
- signals are the same in replay and streaming;
- `live-*` statuses are reserved and trade only virtual books;
- the `auspex-strategy` key layout (the README table), for the keys the archived spec did not name: `funnel/` and `risk/catalyst_holds.jsonl`.

**DSH:**
- the upstream timeout;
- the hash comparison for an unknown username;
- token-less scraper and price writes, under the localhost threat model.

**Owner questions:**
- Is the capital allocator still intended?
- Should the runtime refuse `live-*` statuses until live trading exists?

The owner records the approval as `## <date> — Living docs — CHOICE — strategy-and-dashboard ratification batch`. Once that CHOICE exists, the cutover (step 3) flips these rows to their real status. This spec appends neither the CHOICE nor the flip.

### 7. Active specs edited

| Spec | Edit |
|---|---|
| `forward-paper-trading` | **Docs impact:** `STR-new` (paper ledger, close-out, heartbeats, gap detection and tier books, which go in `runtime.md` when the spec merges). It changes the restart-idempotency row in `runtime.md` and the runtime-wiring row in `risk.md`, and uses the EVA forward-check IDs. **Constraints:** the INV-2, INV-9 and INV-14 citations stay; "Point-in-time…" becomes the STR as-of ID and the RES entry-timing ID. **Fixes:** the Context link `specs/decision-trace.md` becomes `specs/done/decision-trace.md`. **Blocked by:** drop the met items 1–6 (`strategy-runtime`, `backtest-look-ahead-fix`, pre-registration, `realistic-cost-model`, `slow-signal-preregistration` and `cross-sectional-portfolio-backtest` are all done) and renumber the rest (golden-set calibration, data refresh, catalyst panel, and the recommended company-program item). |
| `live-trading` | **Docs impact:** `STR-new` (orders, reconciliation, live kill switches). It retires or changes the STR ID for "`live-*` reserved". **Sections:** rename `## What this builds (to be scoped)` to `## What this builds`, and put "To be scoped." as its first body line. **Fixes:** the Context line "`VirtualBook` with a `mode=live` book" cites the STR ID instead (the mode exists but is unused). **Constraints:** "Invariant 6 (broker credentials only in `.env` and Airflow Connections)" becomes INV-6 as worded in `docs/system/invariants.md`. Stays `draft`. |
| `ingestion-config-ui` | **Docs impact:** DSH (new pages); HUB and ING (the config API owned by `managed-ingestion-config`). **Constraints:** "Pre-registration: `/research-config` reads… never writes" becomes the EVA read-only ID; the INV-2 and INV-9 citations stay. **Blocked by:** drop `specs/dashboard-foundation.md` (done); `specs/managed-ingestion-config.md` stays. |
| `signal-browse-views` | **Docs impact:** DSH (views), HUB (endpoints). **Constraints:** "§4.1: superseded corroborations never appear" becomes the COR or HUB ID; "§3.11" and Invariant 12 become INV-12 plus the HUB validation ID. **Blocked by:** both blockers are done (`graph-and-connector-wiring-fixes`, `dashboard-foundation`); the field becomes "None outstanding". The status stays as `TODO.md` has it; the PR body notes that the owner can set it `ready`. |
| `pipeline-control-view` | **Docs impact:** DSH; OPS (Airflow API user, re-extraction DAG); ING. **Constraints:** "§5: … never write `cursor:{source_type}`" becomes the ING cursor ID and the OPS orchestration ID; "§3.3: no `raw_content`" becomes its HUB or CON ID; the INV-3, INV-6 and INV-11 citations stay. **Blocked by:** both blockers are done (`dashboard-foundation`, `graph-and-connector-wiring-fixes`); the field becomes "None outstanding", status unchanged, noted in the PR body. |
| `lineage-trace-view` | **Docs impact:** DSH, HUB, COR (evidence tables, reproducible score). **Constraints:** "Invariant 10 and §3.7", "§4.1" and "§4.2" become INV-10 plus the CON natural-key ID and the COR IDs; the INV-2, INV-5, INV-9 and INV-12 citations stay. **Blocked by:** drop `graph-and-connector-wiring-fixes` (done); `specs/signal-browse-views.md` stays. |
| `research-results-view` | **Docs impact:** DSH; STR (results read API, `STR-new`); EVA. **Sections:** rename `## What this builds (to be confirmed at scoping)` to `## What this builds` and `## Required tests (provisional; confirm at scoping)` to `## Required tests`, each with its qualifier as the first body line. **Constraints:** "Pre-registration: … never recomputes a verdict" becomes the EVA read-only and verdict IDs; "Every statistic carries its `n`" becomes the STR metrics ID. **Fixes:** `specs/decision-trace.md` becomes `specs/done/decision-trace.md`; drop `strategy-runtime` and `evaluation-protocol` from Blocked by (both done). Stays `draft`. |

**Rule for other domains' requirements.** Cite a HUB, COR, ING, OPS or CON requirement by its ID when that ID exists on the integration branch. Otherwise cite the owner doc as a file link, for example `docs/core-hub/http-api.md`. Never write an `<NS>-?` placeholder. List each file-level link in the PR body, so that the cutover reconciliation can narrow it to an ID.

### 8. Shared files: only this spec's sections

- **`specs/living-docs-cutover-matrix.md`:**
  - Fill the `ID` cell of every row whose `NS` cell is STR or DSH and whose disposition is move, ratify, divergent or retire.
  - In the Decisions table, append to the `IDs` cell of every row classified `binding` the STR and DSH IDs whose `Source` cites that heading, separated by spaces. Keep IDs other specs wrote.
  - Edit no other cell.
- **`docs-check.toml`:** as the last step, remove `"strategy"` and `"dashboard"` from `[rollout] planned_domains`. Change no other line.
- **`TODO.md`:** change only this spec's row: Status `done`, link `specs/done/living-docs-strategy-and-dashboard.md`.
- **This spec:** move it to `specs/done/living-docs-strategy-and-dashboard.md`, with Status `done`, in this PR.
- **`docs/README.md`** is owned by `specs/living-docs-system-and-contracts.md`. This spec does not edit it.

## Out of scope

- Any code change. Each of these is a fix spec after the rollout, opened from the defects-found PENDING entry:
  - the stale `AsOfContext` docstring;
  - wiring the risk layer or the tracer;
  - the input-health endpoint;
  - book idempotency;
  - a runtime DLT;
  - BFF path containment.
- `docs/strategy/paper-trading.md` or `live-trading.md`. Neither is created until its spec is implemented.
- The write-token and no-CORS requirement text (owned by `specs/living-docs-core-hub.md`).
- `docs/README.md` (owned by `specs/living-docs-system-and-contracts.md`).
- Trimming `services/strategy/README.md` and `services/dashboard/README.md` (`specs/legacy-docs-retirement.md`), and the `CLAUDE.md` trap entries (`specs/agent-instruction-hierarchy.md`).
- `config/strategies/registry.yaml` and `config/themes.yaml` values.
- Any text for a sixteenth invariant. It is written only by the cutover (step 3), and only if the owner's CHOICE adopts it.

## Constraints

- **INV-15: docs are not proof.** Each `tested` row names a test read in the code. Every code fact above is re-read at the rollout base before its row is written.
- **Conversion provenance** (`specs/living-docs-cutover-design.md` §8.5).
  - Each `Source` is a requirements §, a `CHOICE` heading, an archived spec, an invariant or an owner ratification.
  - Rules found only in code or a README go to the batch as `pending-decision`.
  - A source that contradicts the code is written as approved and marked `divergent` with a `DECISIONS.md` heading. It never silently follows the code.
- **Conflict policy.** Locked machine authorities win on values: protocol `sizing` and `instruments`, and the hypothesis known-at delays.
  - **INV-11 and the runtime's skip.** A `DECISIONS.md` CHOICE cannot narrow an invariant. The skip is `divergent` until `invariants.md` carries an exception or a fix lands.
  - **INV-10 and restart duplicates.** The same rule applies.
- **Single owner.** These are linked, never restated:
  - the write token and no CORS (HUB);
  - the corroborated wire format and DLT naming (CON).

  The as-of processing-time rule is split between RES's aligner and STR's context. Each states its own mechanism and links the other.
- **No registered value in prose.** Protocol ceilings, `min_trades_for_kelly`, budgets and the theme map are named by file and key.
- **ID rules.**
  - IDs are allocated with `--next`.
  - Each is defined once, and keeps its number when reworded.
  - No register number (`D-` followed by two digits) appears in `docs/` or in any spec this spec edits. Decisions are cited by heading.
  - On a post-rebase collision, renumber this spec's IDs everywhere it wrote them.
- **Citations in verification-table cells are always in backticks,** as check K requires. A heading is written as in `DECISIONS.md`; a heading that itself contains backticks is cited with double backticks, for example ``## 2026-10-07 — Startup data — CHOICE — data fills itself on `up`; prices refresh daily``.
- **No plan-step names.**
- **Deliberate defects** used to prove a test run only in a copy under `${TMPDIR:-/tmp}`. Nothing is committed or pushed.

## Dependencies

- **Needs:**
  - the four specs in Blocked by;
  - the `DECISIONS.md` headings listed there.
- **Hands to later specs:**
  - `specs/agent-instruction-hierarchy.md`: `services/strategy/AGENTS.md` and `services/dashboard/AGENTS.md` list these IDs.
  - `specs/legacy-docs-retirement.md`: links the two READMEs to these IDs.
  - `specs/living-docs-cutover.md`:
    - runs check M on the STR and DSH rows;
    - flips the batch rows after the owner answers;
    - narrows the file-level links in this PR body to IDs.
  - The fix specs opened from the defects-found entry: docstring, risk wiring, tracer, input health, idempotency, DLT, path containment.

## Affected files

| Path | Action |
|---|---|
| `docs/strategy/contract.md` | create |
| `docs/strategy/runtime.md` | create |
| `docs/strategy/risk.md` | create |
| `docs/strategy/decision-trace.md` | create |
| `docs/dashboard.md` | create |
| `specs/forward-paper-trading.md` | modify |
| `specs/live-trading.md` | modify (incl. the `What this builds` heading) |
| `specs/ingestion-config-ui.md` | modify |
| `specs/signal-browse-views.md` | modify |
| `specs/pipeline-control-view.md` | modify |
| `specs/lineage-trace-view.md` | modify |
| `specs/research-results-view.md` | modify (incl. the `What this builds` and `Required tests` headings) |
| `specs/living-docs-cutover-matrix.md` | modify: the `ID` cells of rows with NS STR or DSH; STR/DSH IDs appended to the binding Decisions-table `IDs` cells |
| `docs-check.toml` | modify: `[rollout] planned_domains`, remove `"strategy"` and `"dashboard"` only |
| `DECISIONS.md` | modify (append one entry: strategy-and-dashboard ratification batch) |
| `TODO.md` | modify (this spec's row only) |
| `specs/living-docs-strategy-and-dashboard.md` → `specs/done/living-docs-strategy-and-dashboard.md` | move, Status `done` |
| `services/strategy/**`, `services/dashboard/**`, `config/strategies/registry.yaml`, `config/themes.yaml`, `docker/docker-compose.yml` | untouched, cited |
| `docs/README.md`, `docs/core-hub/http-api.md`, `docs/research/*.md`, `docs/system/*.md` | untouched, linked |

## Required tests

All of these run from the repo root with `python3 -m tools.docs_check`, which `specs/docs-check-tooling.md` creates. That spec defines the selectors `--only`, `--paths` (a comma list of globs), `--matrix`, `--domain` and `--decisions`.

`$OWN` stands for this spec's own files:

```text
docs/strategy/**,docs/dashboard.md,specs/forward-paper-trading.md,specs/live-trading.md,specs/ingestion-config-ui.md,specs/signal-browse-views.md,specs/pipeline-control-view.md,specs/lineage-trace-view.md,specs/research-results-view.md,specs/done/living-docs-strategy-and-dashboard.md
```

- **`strategy_and_dashboard_files_pass_structure_ids_and_links`.** Runs `python3 -m tools.docs_check --only A,B,C,D,E,K --paths "$OWN"`. It fails on:
  - a missing required H2 or `Docs impact` in a doc or in one of the seven edited specs;
  - a bad `Last reviewed against`;
  - a duplicate or unresolved ID;
  - a register number or an `NS-?` placeholder;
  - a missing backticked path;
  - a `tested` row whose test name is absent;
  - a `divergent` row without an existing `DECISIONS.md` heading.
- **`matrix_rows_for_strategy_all_have_assigned_ids`.** Runs `python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain STR`.
- **`matrix_rows_for_dashboard_all_have_assigned_ids`.** The same, with `--domain DSH`.
- **`binding_decisions_carried_by_strategy_and_dashboard_ids`.** Runs `python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --decisions --domain STR`, and the same with `--domain DSH`. It fails when:
  - a binding Decisions row with an STR or DSH fragment row has no STR or DSH ID in its `IDs` cell;
  - or that ID's `Source` does not contain the heading text.
- **`as_of_requirement_states_the_approved_behaviour_and_cites_its_decision`.** In `contract.md`, the as-of requirement's verification row cites `Living docs — PENDING — as-of reads hide or raise`, or its CHOICE.
  - Under the default (hide), its status is `tested`, citing `test_runtime_components.py::test_backtest_context_hides_records_not_yet_known`, and Known traps names `abc.py`.
  - It fails if the requirement says "raises" while the decision is "hide", or if no decision is cited.
- **`runtime_gaps_are_divergent_rows_citing_decisions`.** These rows exist with status `divergent`, each citing an existing heading:
  - `risk.md`: runtime risk review and capital allocation;
  - `decision-trace.md`: paper and live tracing;
  - `runtime.md`: input-health provider, restart idempotency, unreadable events (INV-11) and live ticker and source types;
  - `contract.md`: versioning in production.

  It fails if any row is `tested` or `untested`, or lacks a heading.
- **`write_token_and_cors_are_linked_not_restated`.** Every line of `docs/dashboard.md` matching `-i 'write token|CORS'` also contains `core-hub/http-api.md`. Check C finds no DSH ID whose text defines the token comparison or the CORS rule. It fails on a restatement.
- **`strategy_docs_are_exactly_the_four_planned`.** `ls docs/strategy/*.md | sort` prints exactly:
  - `docs/strategy/contract.md`;
  - `docs/strategy/decision-trace.md`;
  - `docs/strategy/risk.md`;
  - `docs/strategy/runtime.md`.

  This fails before the work (no directory) and if a paper-trading or live-trading doc was added.
- **`no_registered_value_restated_in_strategy_docs`.** `grep -nE '0\.25|0\.05|max_kelly_fraction: |min_trades_for_kelly: |small_cap_biotech' docs/strategy/*.md` prints nothing outside a key name in backticks. The full pattern list is fixed in the PR body. It fails on a copied value.
- **`stale_spec_paths_fixed_in_dashboard_and_strategy_specs`.** Over the seven edited specs, `grep -nE 'specs/(decision-trace|dashboard-foundation|strategy-runtime)\.md'` prints nothing; every hit must be `specs/done/...`.
- **`done_blockers_dropped_from_edited_specs`.** In the `**Blocked by:**` field (up to `**Branch:**`) of the seven edited specs, `grep -nE '(dashboard-foundation|graph-and-connector-wiring-fixes|strategy-runtime|backtest-look-ahead-fix|realistic-cost-model|slow-signal-preregistration|cross-sectional-portfolio-backtest)'` prints nothing. It fails if a done blocker is left.
- **`edited_draft_specs_have_exact_section_names`.** For `specs/live-trading.md` and `specs/research-results-view.md`:
  - `grep -cE '^## (Context|What this builds|Out of scope|Constraints|Required tests|Definition of done)$'` prints `6`;
  - `grep -cE '^## (What this builds|Required tests) \('` prints `0`.
- **`strategy_and_dashboard_code_untouched`.** `git diff --exit-code "$(git merge-base HEAD origin/feature/living-docs-integration)" -- services/ config/ docker/ docs/README.md`.
- **`strategy_and_dashboard_planned_domains_removed`.** This fails if either domain is still listed:

  ```bash
  python3 -c "import tomllib;d=tomllib.load(open('docs-check.toml','rb'));p=d['rollout']['planned_domains'];assert 'strategy' not in p and 'dashboard' not in p"
  ```
- **`at_risk_rules_in_strategy_map_to_ids`.** Check M covers the matrix rows for these rules, each of which must carry an ID that check C finds:
  - processing time (STR side);
  - deterministic intent ids and one `DocumentRecord` per participant;
  - risk check order, units and unmapped-theme rejection.

  The test is listed so a reviewer reads those rows.

**Falsify the TypeScript test-name resolution once.** In a copy of the tree under `${TMPDIR:-/tmp}`, change one `auth.test.ts::` name in the copy's `dashboard.md` to a name that does not exist. Check K on the copy must report it.

## Definition of done

```bash
OWN='docs/strategy/**,docs/dashboard.md,specs/forward-paper-trading.md,specs/live-trading.md,specs/ingestion-config-ui.md,specs/signal-browse-views.md,specs/pipeline-control-view.md,specs/lineage-trace-view.md,specs/research-results-view.md,specs/done/living-docs-strategy-and-dashboard.md'
python3 -m tools.docs_check --only A,B,C,D,E,K --paths "$OWN"
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain STR
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain DSH
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --decisions --domain STR
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --decisions --domain DSH
git diff --exit-code "$(git merge-base HEAD origin/feature/living-docs-integration)" -- services/ config/ docker/ docs/README.md
ls docs/strategy/*.md | wc -l
test -f docs/dashboard.md && echo dashboard ok
python3 -c "import tomllib;d=tomllib.load(open('docs-check.toml','rb'));p=d['rollout']['planned_domains'];assert 'strategy' not in p and 'dashboard' not in p;print('planned ok')"
```

Expected:
- the five checker runs print nothing and exit 0;
- `git diff` exits 0;
- the `ls` count prints `4`;
- the next two lines print `dashboard ok` and `planned ok`.

The `planned_domains` edit is the last commit.

The PR body lists:
- the ratification-batch heading;
- each `divergent` row with its heading;
- each file-level link to another domain's doc that still waits for an ID;
- the value pattern list.

## Compatibility

- **READMEs and agent files are unchanged** until `specs/legacy-docs-retirement.md` and `specs/agent-instruction-hierarchy.md` merge.
- **Nothing reaches `develop` before the cutover.** Source: `## 2026-10-15 — Living docs — PENDING — rollout branch model`, or its CHOICE.
- **No code or test changes.** Strategy CI (`python.yml`, strategy job) and dashboard CI (`dashboard.yml`) see no diff.
- **Edited specs keep their paths.** Only stale path text and two section headings inside them change. The archived specs they link stay at `specs/done/`.
- **If the as-of decision is answered "raise" after this spec merges:**
  - the as-of ID is retired;
  - a new ID with the reversed meaning is added, with status `divergent`;
  - no other doc changes.

## Rollback

Run this on the integration branch, before the cutover. The range runs from the integration-branch tip before this spec merged to the tip after it, so it includes this spec's first commit.

```bash
git revert --no-commit <integration tip before merge>..<integration tip after merge>
git restore --staged --worktree --source=HEAD -- DECISIONS.md
# append to DECISIONS.md:
#   ## <date> — Living docs — FLAG — strategy and dashboard docs rolled back
#   (what was reverted and why; the strategy-and-dashboard ratification batch entry stays as history)
git add DECISIONS.md && git commit
```

The revert:
- removes `docs/strategy/` and `docs/dashboard.md`;
- restores the seven specs, the matrix cells, the two `planned_domains` entries, this spec's `TODO.md` row and its place in `specs/`.

It never deletes a `DECISIONS.md` entry.

If a later spec (`specs/agent-instruction-hierarchy.md` or `specs/legacy-docs-retirement.md`) already links these IDs, revert those links in the same PR. No runtime or data rollback is needed.

## Notes

- **Why this spec waits on core-hub and research.** The dashboard doc must link HUB IDs (write token, no CORS). The four view specs it edits cite HUB and COR requirements, and the strategy docs link RES and EVA. With those specs merged first, most citations are real IDs, not file-level links.
- **Strategy metrics have no file of their own.** They go in `runtime.md`, next to the metrics API. If `runtime.md` grows past one subject, split metrics out in a later change spec.
- **`themes.yaml` covers only the watched tickers.** Portfolio strategies use the protocol sizer, not this risk layer. But any event strategy on a universe ticker is still rejected `THEME_UNMAPPED`. This is recorded as a trap, not as a requirement change.
- **Cite line numbers from the code at the rollout base.** Earlier analysis notes gave slightly different line numbers; for example, `PassThroughRiskManager` is at `runtime/main.py:150` at `e51f742`.
