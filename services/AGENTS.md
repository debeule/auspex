# services

Shared by the six service directories below this one; each has its own `AGENTS.md` with its commands.

## Owners

- Anything on Kafka (topics, keys, payloads, generated fixtures, dead letters): `docs/system/contracts.md`.

## Layout

- `ingestion-scraper/`, `core-hub/`, `backtesting/`, `strategy/`, `backup/`, `dashboard/`.
- Topic names and partition counts: `docker/topics.yaml`.
- Comment form per stack (Java, Python, TypeScript, shell and YAML): ENG-052 in `docs/engineering/conventions.md`.

## Requirements that bite here

- INV-1: the scraper's only stores are MinIO and Kafka.
- INV-2: core-hub alone writes Postgres and Neo4j.
- CON-009: signal fixture generated from the Pydantic model.
- CON-007: raw pointer fixture generated from producer output.
- CON-031: model, Java record and fixture change in one PR.
- CON-035: dead letters go to lowercase `.dlt`.
- CON-004: a DLT has its source topic's partition count.
