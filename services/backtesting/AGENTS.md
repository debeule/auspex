# backtesting

## Owners

- `docs/research/market-data.md`, `docs/research/universe.md`, `docs/research/panels.md`, `docs/research/simulation.md`, `docs/research/backtesting.md`.
- Protocol, hypotheses and trials: `docs/research/evaluation-protocol.md`.

## Commands

Run from `services/backtesting/`.

```bash
uv sync                              # install
uv run pytest tests/unit -q          # unit
uv run pytest tests/integration -q   # integration (Docker, LocalStack S3; CI)
uv run ruff check .                  # lint
```

## Layout

- `src/auspex_backtesting/`: package; `scripts/`: research runs on the stack machine; `dags/`: price refresh and universe build.
- Research config at the repo root: `config/hypotheses/`, `config/universe/`, `config/short_interest/`.

## Requirements that bite here

- EVA-001: protocol and hypotheses hash-locked.
- EVA-006: research config read-only outside the repo.
- RES-014: universe rules pinned per version.
- RES-004: only settled bars stored.
- RES-003: a stored bar is never rewritten.
- RES-067: processing time never decides what a backtest knows.
- RES-026: panel rows carry the instant they became known.
- RES-028: missing data is missing with a reason.
- EVA-022: entity-only variant beside the full one.
- EVA-011: trials reserved in the ledger.

## Trap pointers

- EVA-001: the hash is over raw bytes: `docs/research/evaluation-protocol.md`, Known traps.
- RES-001: yfinance is unofficial and rate-limited: `docs/research/market-data.md`, Known traps.
