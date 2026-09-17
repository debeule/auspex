# Prerequisites — outstanding items

Everything here needs a person before the blocked step can proceed.

---

## ⏳ Credentials needed

| Item | Blocks | How |
|---|---|---|
| **EPO OPS key + secret** | Patent filings connector | Register at `developers.epo.org` (email only, no government ID). Create an application to get `EPO_OPS_KEY` and `EPO_OPS_SECRET`. Free standard tier: 2.5 req/s, 4 GB/week. No commercial-use restriction. |

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

## ✅ Already configured
OpenAI key + billing, NCBI key, openFDA key, `SEC_USER_AGENT`, extraction quality gate (≥0.85 precision), corroboration precision gate (≥0.85 genuine), extraction model (`gpt-4o-mini`).
