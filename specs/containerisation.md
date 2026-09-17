# Full Containerisation

**Status:** ready
**Blocked by:** [Scraper HTTP API](scraper-api.md) — ingestion-scraper must expose `/health` before it can be added to compose; [Centralised logging](centralised-logging.md) — Filebeat ships logs from containers, so structured logging must be in place first
**Branch:** `feature/containerisation`

---

## Context

All infrastructure (Kafka, Postgres, Neo4j, MinIO, Airflow, Elasticsearch, Kibana, Filebeat) already runs in Docker Compose. The two application services — `ingestion-scraper` and `core-hub` — run on the developer's host machine. This spec adds them to the compose stack so the full system can be brought up with a single command and left running stably for weeks.

Two concrete problems in the current compose file that this spec fixes:

**1. Kafka's advertised listener is host-only.** `KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://127.0.0.1:9092` is unreachable from inside any container. After containerisation, `ingestion-scraper` and `core-hub` connect to Kafka from within Docker's network. The fix is a second listener on the Docker-internal hostname.

**2. Airflow volume-mounts the scraper source tree.** The current Airflow container sets `PYTHONPATH: /opt/airflow/python_packages` pointing at a bind-mount of `services/ingestion-scraper/src`. This is fragile — `auspex_ingest`'s third-party dependencies (confluent-kafka, instructor, minio, openai) are not installed in the base Airflow image. After the scraper API spec, the DAG file calls HTTP and the volume mount is removed.

Developer workflow does **not** change during active development. The compose profile system ensures infra-only and full-stack modes coexist.

## What this builds

### 1. `services/ingestion-scraper/Dockerfile`

Multi-stage uv-based Python image:

```dockerfile
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv
FROM python:3.14.2-slim AS runtime

WORKDIR /app
COPY --from=uv /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ ./src/
COPY config/ ./config/
COPY prompts/ ./prompts/

ENV PYTHONPATH=/app/src
EXPOSE 8000
CMD ["uv", "run", "gunicorn", "auspex_ingest.api:create_app()", \
     "--config", "config/gunicorn.conf.py"]
```

`uv sync --frozen --no-dev` reproduces the exact lock file without installing dev/test dependencies. `prompts/` must be included because `LLMExtractor` resolves `_PROMPT_DIR` relative to its source file location.

### 2. `services/core-hub/Dockerfile`

Multi-stage Gradle build:

```dockerfile
FROM eclipse-temurin:25-jdk-alpine AS build
WORKDIR /app
COPY gradlew ./
COPY gradle/ ./gradle/
COPY build.gradle.kts settings.gradle.kts gradle.properties ./
RUN ./gradlew dependencies --no-daemon --quiet
COPY src/ ./src/
RUN ./gradlew bootJar --no-daemon -x test

FROM eclipse-temurin:25-jre-alpine AS runtime
WORKDIR /app
COPY --from=build /app/build/libs/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
```

The build stage caches dependency resolution separately from source compilation. Tests do not run in Docker build (`-x test`) — they run in CI. The runtime stage uses JRE-only (smaller image, no compiler).

### 3. `docker/docker-compose.yml` changes

**Kafka — dual listener:**

```yaml
KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093,INTERNAL://0.0.0.0:9094
KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://127.0.0.1:9092,INTERNAL://kafka:9094
KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT,INTERNAL:PLAINTEXT
KAFKA_INTER_BROKER_LISTENER_NAME: INTERNAL
```

- `PLAINTEXT://127.0.0.1:9092` — host machine access (scripts, IDE, local tools). Unchanged.
- `INTERNAL://kafka:9094` — container-to-container access. App services use `KAFKA_BOOTSTRAP_SERVERS: kafka:9094`.

**New `ingestion-scraper` service** (profile `app`):

```yaml
ingestion-scraper:
  build:
    context: ../services/ingestion-scraper
    dockerfile: Dockerfile
  container_name: auspex-ingestion-scraper
  profiles: ["app"]
  restart: unless-stopped
  depends_on:
    kafka:
      condition: service_healthy
    minio:
      condition: service_healthy
  environment:
    KAFKA_BOOTSTRAP_SERVERS: kafka:9094
    KAFKA_RAW_TOPIC: auspex.raw.ingested
    KAFKA_SIGNALS_TOPIC: auspex.signals.extracted
    MINIO_ENDPOINT: minio:9000
    MINIO_ACCESS_KEY: ${MINIO_ACCESS_KEY}
    MINIO_SECRET_KEY: ${MINIO_SECRET_KEY}
    MINIO_BUCKET: ${MINIO_BUCKET}
    OPENAI_API_KEY: ${OPENAI_API_KEY}
    OPEN_AI_EXTRACTION_MODEL: ${OPEN_AI_EXTRACTION_MODEL}
    LOG_FORMAT: json
  ports:
    - "127.0.0.1:8000:8000"
  healthcheck:
    test: ["CMD-SHELL", "curl -sf http://localhost:8000/health"]
    interval: 10s
    timeout: 5s
    retries: 5
    start_period: 15s
  labels:
    co.elastic.logs/enabled: "true"
```

**New `core-hub` service** (profile `app`):

```yaml
core-hub:
  build:
    context: ../services/core-hub
    dockerfile: Dockerfile
  container_name: auspex-core-hub
  profiles: ["app"]
  restart: unless-stopped
  depends_on:
    postgres:
      condition: service_healthy
    neo4j:
      condition: service_healthy
    kafka:
      condition: service_healthy
  environment:
    SPRING_DATASOURCE_URL: jdbc:postgresql://postgres:5432/${POSTGRES_DB}
    POSTGRES_USER: ${POSTGRES_USER}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    POSTGRES_DB: ${POSTGRES_DB}
    NEO4J_URI: bolt://neo4j:7687
    NEO4J_USER: ${NEO4J_USER}
    NEO4J_PASSWORD: ${NEO4J_PASSWORD}
    KAFKA_BOOTSTRAP_SERVERS: kafka:9094
    LOGGING_STRUCTURED_FORMAT_CONSOLE: ecs
  ports:
    - "127.0.0.1:8080:8080"
  healthcheck:
    test: ["CMD-SHELL", "curl -sf http://localhost:8080/actuator/health"]
    interval: 15s
    timeout: 5s
    retries: 10
    start_period: 45s
  labels:
    co.elastic.logs/enabled: "true"
```

**Airflow changes:**
- Remove volume mounts of `ingestion-scraper/src` and `PYTHONPATH`.
- Add `SCRAPER_API_URL: http://ingestion-scraper:8000`.
- Add `depends_on.ingestion-scraper.condition: service_healthy` (only applies when `app` profile is active — Airflow is always started, so this dependency is conditional on the profile).
- Keep DAG and config volume mounts: `dags/` and `config/` — still needed.

**`restart: unless-stopped` on all services** — recovers from crashes without requiring manual intervention; stops cleanly on `docker compose down`.

### 4. Compose profile convention

| Command | What starts |
|---|---|
| `docker compose up -d --wait` | Infra only (Kafka, Postgres, Neo4j, MinIO, Airflow, Elasticsearch, Kibana, Filebeat) |
| `docker compose --profile app up -d --wait` | Everything including ingestion-scraper + core-hub |

Services without a profile always start. App services use `profiles: ["app"]`.

Update CLAUDE.md commands table to reflect both forms.

### 5. `.env.example` and `VERSIONS.md`

Add:
- `UV_VERSION` — pin the uv image version used in the scraper Dockerfile
- `SCRAPER_API_URL=http://ingestion-scraper:8000` (compose internal) / `http://localhost:8000` (host dev)
- Verify `ELASTIC_VERSION` is already present (from logging spec)

## Out of scope

- Kubernetes, Helm, or cloud deployment.
- TLS between services — internal Docker network, not required.
- Secrets management (Vault, AWS Secrets Manager) — `.env` file is sufficient for local prod-sim.
- CI/CD image building or pushing to a registry — covered by `specs/ci-cd.md`.
- Multi-host or multi-broker Kafka — single broker, RF=1, appropriate for this scale.

## Constraints

- The Kafka dual-listener change must be backward-compatible. Host-side connections (`scripts/run_pipeline.py`, `scripts/reextract.py`, manual Kafka CLI tools) continue using `localhost:9092`. Only containers use `kafka:9094`. Verify both after the change.
- Dockerfiles must not bake in secrets or environment-specific values. All config via environment variables passed through compose.
- `uv sync --frozen` — not `uv sync`. The `--frozen` flag errors if `uv.lock` is out of date rather than silently updating it. The lock file is the source of truth.
- `./gradlew bootJar -x test` — tests are excluded from Docker build. Tests belong in CI, not image build time.
- Core-hub's Spring Boot application.yml uses `${POSTGRES_HOST:localhost}` style substitution. In the container, override via `SPRING_DATASOURCE_URL` environment variable (Spring Boot picks it up automatically). Do not modify `application.yml`.
- Airflow's `depends_on: ingestion-scraper` creates a problem when running infra-only (no `app` profile): Airflow would wait on a service that doesn't exist. Solve with a separate `docker-compose.app.yml` override file or by accepting that Airflow's health check already waits for the API before DAGs run (Airflow starts regardless; DAG runs fail gracefully if scraper is unreachable).
- The scraper container's `prompts/` path: `_PROMPT_DIR` in `extractor.py` resolves relative to the source file. In the container at `/app/src/auspex_ingest/extractor.py`, it resolves to `/app/prompts/extraction/`. This must be present — verify in `test_ingestion_scraper_dockerfile_builds_successfully`.

## Required tests

These are operational/smoke tests, not unit tests. They validate the compose stack, not the application logic (which is covered by each service's own suite).

- `test_ingestion_scraper_image_builds` — `docker build services/ingestion-scraper` exits 0; `/health` route is importable (smoke import, not a live request)
- `test_core_hub_image_builds` — `docker build services/core-hub` exits 0; JAR file is present in build layer
- `test_full_stack_health_checks_pass` — `docker compose --profile app up -d --wait` completes; `docker compose --profile app ps` shows all services `(healthy)`
- `test_host_kafka_access_after_dual_listener` — from host, produce one message to `auspex.raw.ingested` on `localhost:9092`; consume it back; confirm no connection errors
- `test_container_kafka_access` — from inside the `ingestion-scraper` container, POST `/ingest/mock` (if mock source is available) succeeds without Kafka connection errors
- `test_core_hub_actuator_health_returns_up` — `curl http://localhost:8080/actuator/health` returns `{"status":"UP"}`
- `test_ingestion_scraper_restarts_on_crash` — `docker kill --signal=SIGKILL auspex-ingestion-scraper`; within 30 seconds the container is running and `/health` returns 200
- `test_airflow_dag_triggers_ingestion_via_http` — trigger `auspex_biorxiv` DAG manually in Airflow UI; task completes successfully; logs show HTTP 200 response from scraper

## Definition of done

```bash
docker compose --profile app -f docker/docker-compose.yml --env-file .env up -d --wait
docker compose --profile app ps
```

All services show `(healthy)`. Then:

1. Open `http://localhost:8080` — Airflow UI loads.
2. Trigger any ingestion DAG manually.
3. Confirm the task succeeds (green in Airflow).
4. `curl http://localhost:8000/health` — `{"status": "ok"}`.
5. `curl http://localhost:8080/actuator/health` — `{"status": "UP"}`.
6. Open `http://localhost:5601` — Kibana shows log events from both services.

From host (infra-only dev mode verification):
```bash
docker compose down
docker compose up -d --wait
uv run python scripts/run_pipeline.py --sources mock --days 1
```
Runs without error — host connects to Kafka on `localhost:9092`, MinIO on `localhost:9000`.

## Notes

- Airflow `depends_on` the scraper only makes sense when both are started together. When running infra-only, Airflow starts without the scraper — DAG tasks will fail with a connection error until the scraper is running. This is expected and acceptable: the DAG logs the HTTP error, Airflow retries on the next schedule tick, and the scraper can be started separately if needed.
- `eclipse-temurin:25-jre-alpine` is significantly smaller than the JDK image. Pin the exact digest or tag in `VERSIONS.md` once resolved.
- The uv image pin (`ghcr.io/astral-sh/uv:${UV_VERSION}`) is used only in the `FROM` line of the build stage — it does not affect the runtime image. Add `UV_VERSION` to `VERSIONS.md`.
- Gradle dependency caching in Docker: the `RUN ./gradlew dependencies` layer before `COPY src/` ensures dependency jars are cached in a separate layer. A source-only change does not re-download dependencies. This is the standard multi-stage Gradle pattern.
- `LOG_FORMAT: json` in the scraper container forces structlog to emit JSON (not the development console renderer). This is what Filebeat expects.
- After this spec, `docker compose down -v` (wipe volumes) is the reset for a clean state. Document this prominently — wiping volumes deletes all ingested data.
