#!/usr/bin/env bash
# Smoke test for a running Auspex stack.
# Usage: CORE_HUB_URL=http://localhost:8080 ./verify_pipeline.sh
# Exits 0 on success, non-zero on any failure.
set -euo pipefail

CORE_HUB="${CORE_HUB_URL:-http://localhost:8080}"

echo "→ signals REST endpoint reachable ..."
HTTP=$(curl -s -o /dev/null -w "%{http_code}" "${CORE_HUB}/api/v1/signals/ZZZZ")
[ "$HTTP" = "200" ] || { echo "   FAIL: HTTP ${HTTP}"; exit 1; }
echo "   OK (HTTP ${HTTP})"

echo "→ valid-ticker response contains ticker field ..."
BODY=$(curl -s "${CORE_HUB}/api/v1/signals/MRNA")
echo "${BODY}" | grep -q '"ticker"' || { echo "   FAIL: unexpected body: ${BODY}"; exit 1; }
echo "   OK"

echo "verify_pipeline.sh: all checks passed"
