#!/usr/bin/env bash
# Creates every topic declared in topics.yaml. Runs as a one-shot compose service on each `up`;
# --if-not-exists makes a re-run a no-op.
set -euo pipefail

BOOTSTRAP="${KAFKA_BOOTSTRAP:-kafka:9094}"
TOPICS_BIN=/opt/kafka/bin/kafka-topics.sh

# topics.yaml is flat (name, partitions, replication_factor, retention_ms per entry), so awk is
# enough and the Kafka image needs no YAML parser.
awk '
  /- name:/            { name = $3 }
  /partitions:/        { parts = $2 }
  /replication_factor:/{ rf = $2 }
  /retention_ms:/      { print name, parts, rf, $2 }
' /config/topics.yaml | while read -r name partitions rf retention; do
  "$TOPICS_BIN" --bootstrap-server "$BOOTSTRAP" --create --if-not-exists \
    --topic "$name" --partitions "$partitions" --replication-factor "$rf" \
    --config "retention.ms=$retention"
  echo "topic ready: $name (partitions=$partitions, retention_ms=$retention)"
done
