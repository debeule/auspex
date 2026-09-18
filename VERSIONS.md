# Pinned Versions

Verified current as of **2026-08-15**. Anything marked *resolve at 0.0* must be pinned to an exact version during Step 0.0 and written back into this file. **No floating tags, no `latest`, no `>=`.**

## Runtimes
| Component | Pin | Notes |
|---|---|---|
| Python | **3.14.2** | Confirmed 2026-08-15. Airflow 3.2+ supports 3.10–3.14. |
| Java | **25.0.1 (Temurin LTS)** | Confirmed 2026-08-15. Spring Boot 4.1 supports Java 17–26; Neo4j supports Java 25 from 2025.10. |
| Node (Phase 5 only) | *resolve at 5.1* | Not needed before Phase 5. |

## Infrastructure images (pin by digest where possible)
| Component | Pin | Notes |
|---|---|---|
| Kafka | `apache/kafka:4.3.0` | KRaft, no Zookeeper. |
| PostgreSQL | `postgres:18.6` | 18 is current; **19 is in beta — do not use.** |
| Neo4j | `neo4j:2026.05-community` | Neo4j moved to calendar versioning; the 5.x line ended at 5.26 LTS. **See open question 4.** |
| MinIO | `minio/minio:RELEASE.2025-09-07T16-13-09Z` | Resolved 2026-08-15 from `docker pull minio/minio:latest`. |
| Airflow | `apache/airflow:3.3.1` | Phase 2 only. Python 3.14 compatible. |

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

## Python dependencies — ingestion-scraper (`services/ingestion-scraper/`)
Additions resolved 2026-09-18.

| Package | Pinned version |
|---|---|
| structlog | 26.1.0 |

## Python dependencies — backtesting module (`services/backtesting/`)
Managed with **uv**; `uv.lock` is committed. Resolved 2026-09-18 from PyPI.

| Package | Pinned version |
|---|---|
| pandas | 3.0.6 |
| pyarrow | 25.0.1 |
| yfinance | 1.7.0 |
| pandas-datareader | 0.11.1 |
| minio | 7.2.20 (shared with ingestion-scraper) |

## Version-sensitive claims that need re-verification
These were verified against **older** versions than we are now pinning. Confirm each at the step that depends on it and record the outcome in `DECISIONS.md`.

| Claim | Verified against | Confirm at |
|---|---|---|
| `DeadLetterPublishingRecoverer` defaults to `.DLT` + same partition; `-1` means "producer chooses" | Spring Kafka 2.x/3.x | Step 1.3 (we are on Spring Kafka 4.1) |
| `@DecimalMin`/`@DecimalMax` are unsupported on `double` | Bean Validation spec + Hibernate Validator | Step 1.3 (sidestepped by `BigDecimal`) |
| `CREATE CONSTRAINT ... IF NOT EXISTS FOR (n:L) REQUIRE ...` | Neo4j 5 | Step 1.3 (we are on Neo4j 2026.05) |
| Spring Data Neo4j `BigDecimal` conversion behaviour | general SDN behaviour | Step 1.3 (sidestepped by an explicit `double` converter) |
| Kafka Streams internal topics are created via AdminClient regardless of `auto.create.topics.enable` | general Kafka behaviour | Step 6.4, if ever reached |
| `failOnNoDiscoveredTests` exists on the `Test` task | recent Gradle | Step 0.0 — if absent on 9.7.0, assert test counts from `build/reports/tests/` instead and record the fallback in `DECISIONS.md` |
