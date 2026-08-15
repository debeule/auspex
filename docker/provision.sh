#!/usr/bin/env bash
# Provisions Kafka topics and the MinIO bucket after compose infra is healthy.
# Run once after: docker compose -f docker/docker-compose.yml --env-file .env up -d --wait
# Safe to re-run: topic creation uses --if-not-exists; bucket creation is idempotent.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found. Copy .env.example and fill in credentials." >&2
  exit 1
fi

# Read a single variable from .env without sourcing the whole file
_env() {
  grep -E "^${1}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

COMPOSE_PROJECT_NAME=$(_env COMPOSE_PROJECT_NAME)
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-auspex}"
KAFKA_CONTAINER="${COMPOSE_PROJECT_NAME}-kafka"

# ── Kafka topics ───────────────────────────────────────────────────────────────
echo "==> Provisioning Kafka topics..."
docker exec -i "$KAFKA_CONTAINER" /bin/bash -s <<'KAFKA_EOF'
set -e
BOOTSTRAP="localhost:9092"
TOPICS_BIN="/opt/kafka/bin/kafka-topics.sh"

for i in $(seq 1 30); do
  "$TOPICS_BIN" --bootstrap-server "$BOOTSTRAP" --list > /dev/null 2>&1 && break
  echo "  Waiting for Kafka broker... ($i/30)"
  sleep 2
done

create_topic() {
  "$TOPICS_BIN" --bootstrap-server "$BOOTSTRAP" \
    --create --if-not-exists \
    --topic "$1" \
    --partitions "$2" \
    --replication-factor 1 \
    --config "retention.ms=$3"
  echo "  topic: $1 (partitions=$2, retention_ms=$3)"
}

create_topic auspex.raw.ingested             6 604800000
create_topic auspex.signals.extracted        6 7776000000
create_topic auspex.signals.corroborated     6 7776000000
create_topic auspex.raw.ingested.dlt         6 2592000000
create_topic auspex.signals.extracted.dlt    6 2592000000
create_topic auspex.signals.corroborated.dlt 6 2592000000
KAFKA_EOF
echo "==> Kafka topics provisioned."

# ── MinIO bucket ───────────────────────────────────────────────────────────────
echo "==> Provisioning MinIO bucket..."
"$HOME/.local/bin/uv" run \
  --project "$REPO_ROOT/services/ingestion-scraper" \
  python - "$ENV_FILE" <<'PYEOF'
import sys
from pathlib import Path

env_file = Path(sys.argv[1])
env = {}
for line in env_file.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _, val = line.partition("=")
    env[key.strip()] = val.strip()

from minio import Minio

endpoint   = env.get("MINIO_ENDPOINT", "localhost:9000")
access_key = env.get("MINIO_ACCESS_KEY", "")
secret_key = env.get("MINIO_SECRET_KEY", "")
bucket     = env.get("MINIO_BUCKET", "auspex-raw")

if not access_key or not secret_key:
    print("ERROR: MINIO_ACCESS_KEY and MINIO_SECRET_KEY must be set in .env", file=sys.stderr)
    sys.exit(1)

mc = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=False)
if not mc.bucket_exists(bucket):
    mc.make_bucket(bucket)
    print(f"  Created bucket: {bucket}")
else:
    print(f"  Bucket already exists: {bucket}")
PYEOF
echo "==> MinIO bucket provisioned."
echo ""
echo "Infrastructure ready."
