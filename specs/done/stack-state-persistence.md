# Stack state persistence

**Status:** done
**Branch:** `feature/stack-state-persistence`

---

## Context

The stack runs from `docker/docker-compose.yml` on the owner's Mac (Docker Desktop, 8 GB). The goal is that `docker compose down`, removing every container and image, and `up` again leaves the system where it was: same data, same resume points, same logins.

An audit on 2026-10-09 (`DECISIONS.md`, "Stack state persistence — FLAG") found that this already holds for the stores themselves. Kafka, Postgres, Neo4j, MinIO, Elasticsearch, Prometheus, Grafana and Airflow's logs all sit on named volumes. Every one-shot job is a no-op when its data exists: `kafka-init` (`--if-not-exists`), `minio-init`, `price-bootstrap` (appends only), the universe build (`UniverseStore.lock_rules` pins `rules.yaml`), Flyway, `Neo4jSchemaInitializer` (`IF NOT EXISTS`) and `postgres-monitor-role`.

What doesn't survive, or is fragile:

1. **Airflow's Fernet key and JWT secret** live in `/opt/airflow/airflow.cfg` inside the container layer. With no `AIRFLOW__CORE__FERNET_KEY` set, Airflow generates a key when it first writes that file (`airflow/configuration.py`). A recreated container generates a different one. Variables and Connections encrypted with the old key, including the ingestion cursors `cursor:{source_type}` that `services/ingestion-scraper/dags/auspex_dags.py` reads, can then no longer be decrypted.
2. **Airflow's admin password.** `airflow standalone` writes `simple_auth_manager_passwords.json.generated` into the container layer, so every recreate prints a new password (`SETUP.md` step 2).
3. **`AIRFLOW__WEBSERVER__SECRET_KEY`** is the Airflow 2 name. Airflow 3 reads `[api] secret_key` (`AIRFLOW__API__SECRET_KEY`).
4. **Kafka consumer offsets expire after 7 days** (broker default `offsets.retention.minutes` = 10080). If the stack is off longer than that, core-hub's groups `corehub-signal` and `corehub-raw` restart from `earliest` and replay up to 90 days. It's safe, because writes are idempotent, but it is slow.
5. **The Kafka cluster ID** is the image's built-in default (`5L6g3nShT-eMCtK--X86sw`, from the `apache/kafka` image's `configureDefaults`). It's stable today, but implicit. A formatted volume refuses to start under a different ID.
6. **The compose project name** comes only from `COMPOSE_PROJECT_NAME` in `.env`. A compose call without `--env-file .env` would run as project `docker`, against empty volumes, which looks like data loss.
7. **Filebeat's registry** (its read positions) is in the container layer. A recreated filebeat re-ships every log line still on disk, which duplicates them in Elasticsearch.
8. **The Airflow database role's password** is set only by `docker/postgres-init/01_airflow.sh`, which runs on an empty volume only. Changing `AIRFLOW_DB_PASSWORD` in `.env` later locks Airflow out.
9. **The docs prescribe `down -v` as a routine fix.** `docker/README.md` and `docker/CLAUDE.md` give it for wrong topic counts, and `SETUP.md` for any password change. `down -v` deletes the append-only price snapshots, the pinned universe, the raw archive and every signal.

Static compose checks follow the pattern in `services/ingestion-scraper/tests/unit/test_stack_observability_config.py`: parse the YAML and `.env.example`, start no container.

## What this builds

After this spec, recreating any container or image keeps:
- Airflow's encryption key, JWT secret, API secret key and admin password. They come from `.env`, or from a named volume for the generated password file. The ingestion cursors stay readable.
- Kafka consumer offsets through any downtime shorter than the longest topic retention, under a cluster ID pinned in compose.
- The project name `auspex`, from the compose file itself.
- Filebeat's read positions, on a named volume.
- The Airflow database role's password, which a one-shot re-applies from `.env` on every `up`. Changing it in `.env` then takes effect on the next `up`.

The docs no longer suggest `down -v` as a fix. They give the targeted step instead: a one-topic `kafka-topics.sh` command, or an in-place password change per store. Every remaining mention of `down -v` says it destroys all data, including price history and the pinned universe.

## Out of scope

- Backups outside Docker Desktop's disk (`specs/stack-backup.md`).
- Ingestion cursor and retry behaviour, DAG schedules, dead-letter handling, memory limits, log rotation and alerting. These belong to the multi-week test run readiness work.
- Regrouping `.env.example`. Add the new variables into the existing grouping with minimal edits.
- The Airflow API user for the dashboard BFF (`specs/pipeline-control-view.md`).
- Pinning the `eclipse-temurin` base images in `services/core-hub/Dockerfile`. That's reproducibility, not state.

## Constraints

- **Invariant 6:** secrets come from `.env` only. Compose holds `${VAR}` references, with no default for any secret. The Kafka cluster ID is not a secret: it stays a literal in compose, because changing it would orphan the volume.
- A required secret uses `${VAR:?message}`, so `up` stops with a clear error rather than starting Airflow with an empty key. With an empty `fernet_key`, Airflow stores Variables in plaintext.
- **No hand-run scripts** (root `CLAUDE.md`, "Where work can run"). Re-applying the Airflow role password is a compose one-shot that's a no-op when nothing changed. Generating the new secrets once is a `SETUP.md` step, like every other secret there.
- **Existing stacks:** a stack that already ran without `AIRFLOW_FERNET_KEY` has Variables encrypted under the generated key. `SETUP.md` tells that owner to copy the current key into `.env` before the first recreate (`docker exec auspex-airflow airflow config get-value core fernet_key`). On a fresh stack, any generated key works.
- The Kafka cluster ID literal must equal the image default (`5L6g3nShT-eMCtK--X86sw`), so a volume formatted before this spec still starts.
- `KAFKA_OFFSETS_RETENTION_MINUTES` is at least the largest `retention_ms` in `docker/topics.yaml`, converted to minutes.
- New services and volumes follow the conventions #29 established: a `mem_limit` from `.env.example` and the `co.elastic.logs/enabled` label. They must keep the memory-budget test green.
- Doc maintenance table in root `CLAUDE.md`: a new Docker service updates `docker/README.md`; a new known trap (the Fernet key) goes into root `CLAUDE.md` known traps and `docker/CLAUDE.md`.

## Required tests

In `services/ingestion-scraper/tests/unit/test_stack_persistence_config.py` (static, no containers):

- `test_every_stateful_service_keeps_its_data_dir_on_a_declared_named_volume`: kafka `/var/lib/kafka/data`, postgres `/var/lib/postgresql`, neo4j `/data`, minio `/data`, elasticsearch `/usr/share/elasticsearch/data`, prometheus `/prometheus`, grafana `/var/lib/grafana`, filebeat `/usr/share/filebeat/data`, airflow `/opt/airflow/logs` and the password file's directory. Each source is a volume declared under top-level `volumes:`, not a bind mount, not anonymous, not `external`.
- `test_airflow_fernet_key_jwt_secret_and_api_secret_key_are_required_env_references`: `AIRFLOW__CORE__FERNET_KEY`, `AIRFLOW__API_AUTH__JWT_SECRET` and `AIRFLOW__API__SECRET_KEY` are each `${VAR:?...}`, and each `VAR` is a key in `.env.example`.
- `test_airflow_uses_no_airflow_2_webserver_options`: no `AIRFLOW__WEBSERVER__*` key in the airflow service environment.
- `test_airflow_password_file_is_on_the_airflow_state_volume`: `AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_PASSWORDS_FILE` points inside the airflow service's named-volume mount.
- `test_kafka_cluster_id_is_pinned_to_the_id_existing_volumes_were_formatted_with`: `CLUSTER_ID` equals `5L6g3nShT-eMCtK--X86sw`.
- `test_kafka_offsets_outlive_the_longest_topic_retention`: `KAFKA_OFFSETS_RETENTION_MINUTES` × 60000 ≥ the largest `retention_ms` in `docker/topics.yaml`.
- `test_compose_file_names_the_project_and_env_example_agrees`: top-level `name` is `auspex`, and `COMPOSE_PROJECT_NAME` in `.env.example` is `auspex`.
- `test_airflow_db_role_job_runs_before_airflow_and_after_postgres`: the role job depends on `postgres: service_healthy`, `airflow` depends on it with `service_completed_successfully`, and it has `restart: "no"`.
- `test_airflow_db_role_script_alters_the_role_from_env_and_creates_it_if_missing`: the script creates the role only when `pg_roles` lacks it, then runs `ALTER ROLE ... PASSWORD` with the password passed as a psql variable (no string-built SQL), and never runs `DROP`.
- `test_docs_never_offer_down_v_as_a_fix`: every line in `README.md`, `CLAUDE.md`, `SETUP.md`, `docker/README.md` and `docker/CLAUDE.md` that contains `down -v` also contains "destroys all data".
- `test_new_secrets_are_documented_in_setup`: `AIRFLOW_FERNET_KEY`, `AIRFLOW_JWT_SECRET` and `AIRFLOW_SECRET_KEY` are in `SETUP.md`'s `.env` table, and the first-run preflight list in `specs/first-run-on-stack-machine.md` checks them.

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit/test_stack_persistence_config.py -q --strict-markers
cd services/ingestion-scraper && uv run pytest tests/unit -q --strict-markers   # whole unit suite, incl. memory budget
```

Expected: 11 passed; the unit suite green.

**On the stack machine** (step 8 of `specs/first-run-on-stack-machine.md` picks this up), after at least one ingestion run has set a cursor:
1. Record `docker exec auspex-airflow airflow variables get cursor:<a source>`, the admin password from the passwords file, and `kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group corehub-signal` offsets.
2. `docker compose --profile app -f docker/docker-compose.yml --env-file .env down` (no `-v`), then `docker rmi apache/airflow:3.3.1 auspex-backtesting` and the scraper and core-hub images, then `up -d --wait` with the profile.
3. Check: the cursor value is unchanged and readable, the admin password is unchanged, the group's committed offsets are unchanged (no reset to earliest), Kafka logs no cluster-ID error, and filebeat ships no duplicate of a log line already indexed before the restart.
Record the outcome as a VERIFIED or FLAG entry in `DECISIONS.md`.

## Notes

- Airflow 3 env names: `AIRFLOW__CORE__FERNET_KEY`, `AIRFLOW__API_AUTH__JWT_SECRET`, `AIRFLOW__API__SECRET_KEY`, `AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_PASSWORDS_FILE`. Confirm each against the 3.3.1 config reference before wiring it (`airflow config list --defaults` inside the image, or the docs for that version). Record any renamed option in `DECISIONS.md`.
- Generating a Fernet key without Python: `openssl rand -base64 32 | tr '+/' '-_'` (32 random bytes, URL-safe base64, which is the Fernet key format).
- The password-file volume (`airflow_state`) holds only that file. The generated password stays in it until the volume is deleted. `SETUP.md`'s `cat` command moves to the new path.
- Password changes without `down -v`, for the docs: Postgres superuser via `docker exec auspex-postgres psql -U "$POSTGRES_USER" -c "ALTER ROLE ... PASSWORD ..."` before editing `.env` (the container's local socket is trusted). The Airflow role is handled by the new job. Neo4j via `ALTER CURRENT USER SET PASSWORD FROM ... TO ...` in `cypher-shell`. Grafana via `grafana cli admin reset-admin-password`. MinIO root credentials are read from the environment on every start, so editing `.env` is enough.
- Wrong partition count, without `down -v`: `kafka-topics.sh --alter --partitions N` can only grow a topic. Shrinking one is `--delete` on that topic, then `up` (kafka-init recreates it). That loses the topic's messages only.
