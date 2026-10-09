# Pinned Versions

Verified current as of **2026-08-15**. Anything marked *resolve at install* must be pinned to an exact version when first installed and written back into this file. **No floating tags, no `latest`, no `>=`.**

## Runtimes
| Component | Pin | Notes |
|---|---|---|
| Python | **3.14.2** | Confirmed 2026-08-15. Airflow 3.2+ supports 3.10–3.14. |
| Java | **25.0.1 (Temurin LTS)** | Confirmed 2026-08-15. Spring Boot 4.1 supports Java 17–26; Neo4j supports Java 25 from 2025.10. |
| Node | **24.21.0** | Resolved 2026-10-09 (latest 24.x patch; 24 is the Active LTS line, supported to 2028-04). Dashboard service only (`services/dashboard/`): `.nvmrc`, `package.json` `engines`, `@types/node` 24.x and the image `node:24.21.0-alpine3.24`. |

## Infrastructure images (pin by digest where possible)
| Component | Pin | Notes |
|---|---|---|
| Kafka | `apache/kafka:4.3.0` | KRaft, no Zookeeper. |
| PostgreSQL | `postgres:18.6` | 18 is current; **19 is in beta — do not use.** |
| Neo4j | `neo4j:2026.05-community` | Neo4j moved to calendar versioning; the 5.x line ended at 5.26 LTS. **See open question 4.** |
| MinIO | `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z` | Compose stack only. quay.io requires auth — not usable in CI without secrets. |
| LocalStack (testcontainers) | `localstack/localstack:4.9.2` | Integration tests only; CI pulls it through `mirror.gcr.io` (`TESTCONTAINERS_HUB_IMAGE_NAME_PREFIX`). Replaces minio/minio (removed from Docker Hub; quay.io requires auth). **Do not move to calendar-versioned tags (`2026.x`)** — from 2026.03 the image exits with code 55 unless `LOCALSTACK_AUTH_TOKEN` is set. 4.9.2 is the last tag verified to start without a licence (2026-10-07). |
| Airflow | `apache/airflow:3.3.1` | Orchestration (ingestion, price refresh, universe build DAGs). Python 3.14 compatible. |
| Ollama (host, not a container) | *resolve at install* | Local extraction model server. Record `ollama --version` here when installed (`docs/local-model-runbook.md`). Model weights are pinned by digest in `config/models/registry.yaml`, not here. |

## Java dependencies
| Component | Pin | Notes |
|---|---|---|
| Spring Boot | **4.1.0** | **Spring Boot 3.5 reached EOL 2026-06-30.** 4.1 pulls Spring Framework 7, Spring Kafka 4.1, Spring Security 7.1, Hibernate 7.4, Jackson via the 4.1 BOM. |
| Build tool | **Gradle 9.7.0** + committed wrapper, **Kotlin DSL** | Latest stable (2026-08-06). Runs on JVM 17–26, so Java 25 is fine. Versions declared in `gradle/libs.versions.toml` and kept in sync with this file. |
| Testcontainers | **1.21.3** | Resolved 2026-08-15 from Maven Central. Not managed by Spring Boot BOM — pin explicitly in version catalog. |
| ArchUnit | **1.4.1** | Resolved 2026-08-15 from Maven Central. Not managed by Spring Boot BOM — pin explicitly in version catalog. |
| Awaitility | via Spring Boot 4.1 BOM | BOM-managed; do not pin separately. |
| Flyway | via Spring Boot 4.1 BOM | BOM-managed; do not pin separately. Flyway 13.3.0 is current on Maven Central — record for awareness. |
| Lombok | **omitted** | **See open question 6** — Java 25 records plus constructor injection cover our use, and Lombok has historically lagged new JDK releases. |

## Python dependencies
Managed with **uv**; `uv.lock` is committed and is the source of truth. Versions below resolved 2026-08-15 from PyPI. The locked versions in `uv.lock` are authoritative; these are the target upper bounds for `pyproject.toml` pinning.

| Package | Pinned version |
|---|---|
| httpx | 0.28.1 |
| pydantic | 2.13.4 |
| confluent-kafka | 2.15.0 |
| minio | 7.2.20 |
| instructor | 1.15.4 |
| openai | 2.54.0 |
| feedparser | 6.0.14 |
| python-dotenv | 1.2.2 |
| pyrate-limiter | 4.4.0 |
| pytest | 9.1.1 |
| pytest-cov | 7.1.0 |
| pytest-mock | 3.15.1 |
| pytest-socket | 0.8.0 |
| respx | 0.23.1 |
| testcontainers | 4.15.0 |
| ruff | 0.16.3 |
| mypy | 2.3.1 |

## Observability stack
| Component | Pin | Notes |
|---|---|---|
| Elasticsearch | **8.17.3** | Resolved 2026-09-18. Elasticsearch, Filebeat, and Kibana (future) must pin the same version via `ELASTIC_VERSION` in `.env.example`. |
| Filebeat | **8.17.3** (same as above) | Docker autodiscovery; ships container stdout to Elasticsearch. |
| Prometheus | **v3.14.0** | Resolved 2026-09-18 from `prom/prometheus:latest`. |
| Grafana | **13.0.2** | Resolved 2026-09-18 from `grafana/grafana-oss:latest`. |
| curl (elasticsearch-setup init container) | **8.15.0** | Resolved 2026-10-07; replaces a floating `latest` tag. |
| node-exporter | **v1.12.1** (`prom/node-exporter`) | Resolved 2026-10-09 from Docker Hub. Docker VM metrics and the volume-size textfile. The Mac's own `node_exporter` is a Homebrew install (`SETUP.md`), not pinned here. |
| cAdvisor | **0.57.0** (`ghcr.io/google/cadvisor`) | Resolved 2026-10-09 from ghcr.io; arm64 build included. Docker Hub's `gcr.io` mirror stops at v0.55. |
| postgres-exporter | **v0.20.1** (`prometheuscommunity/postgres-exporter`) | Resolved 2026-10-09. |
| kafka-exporter | **v1.10.0** (`danielqsj/kafka-exporter`) | Resolved 2026-10-09. |
| elasticsearch-exporter | **v1.11.0** (`prometheuscommunity/elasticsearch-exporter`) | Resolved 2026-10-09. |
| blackbox-exporter | **v0.28.0** (`prom/blackbox-exporter`) | Resolved 2026-10-09. v0.29.0 was two days old and is skipped until it has settled. |
| statsd-exporter | **v0.31.0** (`prom/statsd-exporter`) | Resolved 2026-10-09. Converts Airflow's statsd metrics. |
| busybox (volume-usage) | **1.37.0** | Resolved 2026-10-09. Runs `docker/volume-usage/collect.sh`. |
| uv (Docker build stage) | **0.12.17** | Resolved 2026-09-18 from `ghcr.io/astral-sh/uv:latest`. Scraper Dockerfile only — does not affect host `uv`. |
| eclipse-temurin JRE | **25.0.4** (tag `25-jre-alpine`) | Resolved 2026-09-18. Runtime image for core-hub container. |

## Python dependencies — ingestion-scraper (`services/ingestion-scraper/`)
Additions resolved 2026-09-18.

| Package | Pinned version |
|---|---|
| structlog | 26.1.0 |
| flask | 3.1.3 |
| gunicorn | 26.2.0 |
| prometheus-client | 0.26.0 |

## Python dependencies — backtesting module (`services/backtesting/`)
Managed with **uv**; `uv.lock` is committed. Resolved 2026-09-18 from PyPI.

| Package | Pinned version |
|---|---|
| pandas | 3.0.6 |
| pyarrow | 25.0.1 |
| yfinance | 1.7.0 |
| pandas-datareader | 0.11.1 |
| pandas-market-calendars | 5.4.0 (resolved 2026-10-07; 5.5.0 skipped, released 2026-10-05) |
| pyyaml | 6.0.3 (same as ingestion-scraper; `load_hypothesis` and the pre-registration tests read hypothesis YAML) |
| minio | 7.2.20 (shared with ingestion-scraper) |
| prometheus-client | 0.26.0 (shared with ingestion-scraper) |
| flask | 3.1.3 (same as ingestion-scraper; price refresh API) |
| gunicorn | 26.2.0 (same as ingestion-scraper) |

## Version-sensitive claims that need re-verification
These were verified against **older** versions than we are now pinning. Confirm each when the code that depends on it is touched and record the outcome in `DECISIONS.md`.

| Claim | Verified against | Confirm at |
|---|---|---|
| `DeadLetterPublishingRecoverer` defaults to `.DLT` + same partition; `-1` means "producer chooses" | Spring Kafka 2.x/3.x | core-hub DLT resolver (we are on Spring Kafka 4.1) |
| `@DecimalMin`/`@DecimalMax` are unsupported on `double` | Bean Validation spec + Hibernate Validator | signal DTO validation (sidestepped by `BigDecimal`) |
| `CREATE CONSTRAINT ... IF NOT EXISTS FOR (n:L) REQUIRE ...` | Neo4j 5 | Neo4j schema setup (we are on Neo4j 2026.05) |
| Spring Data Neo4j `BigDecimal` conversion behaviour | general SDN behaviour | graph writes (sidestepped by an explicit `double` converter) |
| Kafka Streams internal topics are created via AdminClient regardless of `auto.create.topics.enable` | general Kafka behaviour | Kafka Streams correlation spec, if ever built |

## Dashboard dependencies (`services/dashboard/`)
Managed with **npm**; `package-lock.json` is committed and authoritative. Exact versions in `package.json`. Resolved 2026-10-09 from npm; `npm audit --omit=dev --audit-level=high` reports 0 (see `DECISIONS.md` for the dev-only residual).

| Package | Pinned version |
|---|---|
| next | 16.4.0 |
| react / react-dom | 19.3.0 |
| bcryptjs | 3.0.3 |
| typescript | 5.8.3 |
| eslint / eslint-config-next | 9.39.1 / 16.4.0 |
| tailwindcss / @tailwindcss/postcss | 4.3.3 |
| vitest | 5.0.3 |
| vite / @vitejs/plugin-react | 8.3.4 / 6.1.2 |
| @testing-library/react | 16.3.3 |
| jsdom | 26.1.0 |
