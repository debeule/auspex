#!/bin/sh
# Writes the size of every directory under VOLUMES_DIR (one per named compose volume) as
# auspex_volume_bytes for node-exporter's textfile collector, every INTERVAL_SECONDS.
# cAdvisor cannot report volume sizes under Docker Desktop's VM, so this walks them with du.
set -eu

: "${VOLUMES_DIR:=/volumes}"
: "${OUTPUT_FILE:=/textfile/volumes.prom}"
: "${INTERVAL_SECONDS:=900}"

collect() {
  tmp="${OUTPUT_FILE}.$$.tmp"
  {
    echo "# HELP auspex_volume_bytes Bytes used by a named compose volume."
    echo "# TYPE auspex_volume_bytes gauge"
    for dir in "$VOLUMES_DIR"/*/; do
      [ -d "$dir" ] || continue
      name=$(basename "$dir")
      # du -k is POSIX; -b is not in every du.
      kib=$(du -sk "$dir" | cut -f1)
      echo "auspex_volume_bytes{volume=\"$name\"} $((kib * 1024))"
    done
  } > "$tmp"
  # Rename so node-exporter never reads a half-written file.
  mv "$tmp" "$OUTPUT_FILE"
}

if [ "${1:-}" = "--once" ]; then
  collect
  exit 0
fi

while true; do
  collect
  sleep "$INTERVAL_SECONDS"
done
