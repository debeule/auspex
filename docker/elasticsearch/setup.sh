#!/bin/sh
set -e

ES_URL="${ELASTICSEARCH_URL:-http://elasticsearch:9200}"
POLICY_NAME="auspex-logs-ilm"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

until curl -sf "${ES_URL}/_cluster/health" | grep -qE '"status":"(green|yellow)"'; do
  echo "Waiting for Elasticsearch..."
  sleep 3
done

curl -sf -X PUT "${ES_URL}/_ilm/policy/${POLICY_NAME}" \
  -H "Content-Type: application/json" \
  -d "@${SCRIPT_DIR}/ilm_policy.json"

# New daily indices get the policy from Filebeat's index template; this covers indices
# created before the template carried it.
curl -sf -X PUT "${ES_URL}/auspex-logs-*/_settings?allow_no_indices=true" \
  -H "Content-Type: application/json" \
  -d "{\"index.lifecycle.name\": \"${POLICY_NAME}\"}"

echo "ILM policy ${POLICY_NAME} applied."
