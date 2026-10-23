# backup

## Owners

- `docs/operations/backup.md`; restore steps in `docs/backup-restore.md`.
- The restore exception under INV-2: `docs/system/invariants.md`.

## Commands

Run from `services/backup/`.

```bash
uv sync                                  # install
uv run ruff check . && uv run mypy src   # lint + types
uv run pytest tests/unit -q              # fakes, no containers
uv run pytest tests/integration -q       # Postgres, Neo4j and LocalStack containers (Docker; CI)
```

## Layout

- `src/auspex_backup/`: package; `dags/`: the nightly `auspex_backup` DAG.

## Requirements that bite here

- INV-2: restore only into empty stores.
- OPS-069: the backup only reads the stores.
- INV-12: parameterised queries.
- OPS-070: Cypher labels checked against a pattern.
- OPS-064: MinIO mirror additive and undated.
- OPS-067: `last_success.json` written last.
- OPS-068: 409 while a run is in progress.
