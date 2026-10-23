# strategy

## Owners

- `docs/strategy/contract.md`, `docs/strategy/runtime.md`, `docs/strategy/risk.md`, `docs/strategy/decision-trace.md`.

## Commands

Run from `services/strategy/`.

```bash
uv sync                                                   # install
uv run ruff check . && uv run mypy src && uv run pytest tests/unit -q
uv run python -m auspex_strategy kill [--strategy <name>] [--reason <why>] [--reset]
```

The kill switch (Mac) needs the stack's MinIO through `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY`, and no Docker.

## Layout

- `src/auspex_strategy/`: `abc.py` (the contract), `strategies/`, `runtime/`, `risk/`, `trace/`, `metrics/`.
- Strategy config at the repo root: `config/strategies/`, `config/themes.yaml`.

## Requirements that bite here

- STR-003: `AsOfContext` is the only data channel.
- STR-006: processing time never decides an as-of read.
- STR-002: parameters only in the hypothesis file.
- STR-043: risk check order.
- STR-059: deterministic intent ids.
- STR-027: book rows append-only.
- RES-065: market simulation imported from backtesting.
