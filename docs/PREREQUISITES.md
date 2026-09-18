# Prerequisites — outstanding items

Everything here needs a person before the blocked step can proceed.

---

## 👤 Needs your decision

| Item | Blocks | Effort | Notes |
|---|---|---|---|
| **Backfill budget approval** | Historical backfill (Phase 4) | 15 min | Run the dry-run first — it prints document count, estimated LLM calls, and cost. Approve before execution. Configure a budget ceiling in `.env` so the runner aborts rather than overspending. |
| **Broken-PR CI verification** | CI/CD pipeline (Phase 6) | 15 min | Push a deliberately failing test once, confirm CI goes red, revert. Certifies the CI gate is real. |

---

## 🔢 Numbers to set before Phase 4

| Setting | Where | Notes |
|---|---|---|
| One-time backfill budget (dollars) | `.env` as budget ceiling | Set after reviewing the dry-run estimate. |
| Backfill depth | `.env` or CLI flag | Plan default: 24 months. Adjust if you want more or less history. |
| Steady-state LLM budget | `.env` | How many extractions per day is acceptable ongoing. Starter: 500/day. |

---

## Infrastructure (Linux hosts only)

| Setting | How to apply | Notes |
|---|---|---|
| `vm.max_map_count=262144` | `sysctl -w vm.max_map_count=262144` (root) · persist via `/etc/sysctl.d/99-elasticsearch.conf` | Required by Elasticsearch. Docker Desktop (macOS/Windows) sets this automatically inside its VM — Linux hosts must set it manually or Elasticsearch fails to start. |

---

## ✅ Already configured
OpenAI key + billing, NCBI key, openFDA key, `SEC_USER_AGENT`, extraction quality gate (≥0.85 precision), corroboration precision gate (≥0.85 genuine), extraction model (`gpt-4o-mini`), EPO OPS key + secret.
