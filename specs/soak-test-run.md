# Soak test run

**Status:** blocked
**Blocked by:** the stack machine (this spec runs only on the owner's Mac, started there by name in Claude Code); `specs/first-run-on-stack-machine.md` done through its model gate (step 6), so a local model is registered and gated; and `specs/ingestion-run-reliability.md`, `specs/done/dead-letter-recovery.md`, `specs/container-limits-and-log-rotation.md`, `specs/pipeline-alerting-gaps.md` and `specs/infrastructure-observability.md` done on `develop`
**Branch:** `feature/soak-test-run`

---

## Context

Auspex is meant to run unattended for weeks on the owner's MacBook Pro (Apple M4 Pro, 24 GB): the Docker stack in Docker Desktop's VM capped at 8 GB, and the local model in Ollama on the host. Startup data comes from compose one-shots; refreshes come from Airflow DAGs (ingestion per source, `auspex_price_refresh` on NYSE weekdays at 22:30 UTC, `auspex_universe_build` on days 1–7 at 06:00 UTC, `auspex_daily_health` at 07:00 UTC). Grafana alerts and the daily health summary go to the contact point in `.env`.

The soak-test readiness audit (2026-10-09) estimated, before any measurement: Docker VM disk growth of 5 to 20 GB over 21 days, mostly logs; long-running container limits summing to 7,680 MB; Ollama with Llama 3.1 8B Q8 using 9 to 10 GB while loaded (it unloads after 5 idle minutes); so the Mac sits at 21 to 24 GB of 24 GB during extraction.

This run proves the stack keeps working, recovers and stays inside its resources for 21 days without anyone touching it, and records the numbers the estimates were missing.

## What this builds

1. The Mac is prepared to run unattended: no sleep on power, no automatic updates during the run, Docker Desktop and Ollama starting at login with their settings persisted.
2. A 21-day run, spanning a 1st of the month so the universe build runs, with a baseline on day 0, the day-1 peaks measured and fed back into `.env`, a short daily check, and five induced faults in week 2.
3. A report, `docs/soak-test-report.md`, with the measured growth and peaks, every incident with its cause, and a pass or fail against the criteria below, plus VERIFIED or FLAG entries in `DECISIONS.md`.

## Out of scope

- Code changes. A failure caused by a bug is recorded as a FLAG with the exact error, the run continues where it can, and the fix goes through a cloud spec.
- The live historical backfill, strategy runs and paper trading.
- Unpausing `auspex_mock`, or any ingestion DAG, without the owner saying yes in the session.

## Constraints

- Never print secrets: check `.env` keys with `grep -c '^KEY=.\+'`, never `cat .env`. Never commit `.env`.
- `.env` values (limits, thresholds) may be changed on the Mac; tracked files only through this spec's PR (the report, `DECISIONS.md`, `TODO.md`).
- Commits by the owner's identity, no Claude trailers, message style per root `CLAUDE.md`.
- `docker compose down -v`, `docker system prune --volumes` and Docker Desktop's "Clean / Purge data" are forbidden: they delete price history and the pinned universe.
- Invariant 9: every recorded time in UTC.

## Steps

### 1. Prepare the Mac (day −1)
- Power, on the adapter: `sudo pmset -c sleep 0 disksleep 0 powernap 0 standby 0` (display sleep may stay on). Keep the lid open; closed-lid running needs an external display.
- Updates: turn off automatic macOS update installs for the run (System Settings › General › Software Update › Automatic Updates), and Docker Desktop's automatic update download.
- Ollama as a service that keeps its settings across reboots: `brew services` or a LaunchAgent with `OLLAMA_NUM_PARALLEL=1` and `OLLAMA_CONTEXT_LENGTH=8192` in its environment, not `launchctl setenv` (lost at reboot). Confirm after a reboot with `launchctl print` or `ollama ps`.
- Docker Desktop: "Start Docker Desktop when you sign in" on; Resource Saver off; memory 8 GB; note the virtual disk limit.
- FileVault means a reboot waits at the login screen; tell the owner that a power cut or forced restart needs them to log in.
- `node_exporter` on the host (`brew services start node_exporter`) so Mac memory, swap and disk are recorded.
- `.env`: `EXTRACTION_MODEL` is the gated local tag, `OPENAI_API_KEY` is empty, the contact point is set; send a test alert from Grafana and confirm it arrives.

**Check:** `pmset -g` shows `sleep 0` on AC; after one reboot Docker Desktop and Ollama are up without anyone opening them and `ollama ps` reflects the settings; the test alert arrived.

### 2. Baseline (day 0)
Record, with UTC time: `docker system df -v`, per-volume sizes (the volume-usage metric), VM disk free, Mac disk free and swap, Prometheus TSDB size, Airflow cursors (`airflow variables list`), signal counts in Postgres (rows and distinct `event_id`) and Neo4j (`Signal` nodes), DLT end offsets, the latest universe month, the last price bar per refreshed ticker. Then, with the owner's yes, unpause the five live ingestion DAGs (not `auspex_mock`).

**Check:** every service healthy, every Prometheus target up, the first scheduled run of each source starts at its staggered time.

### 3. Measure day 1 and adjust
Over the first 24 hours read from Grafana: peak memory per container (cAdvisor), VM memory p95, Mac swap, and extraction latency p50, p95 and p99. Set each container's `*_MEM_LIMIT` in `.env` to at least 1.3× its peak while the total stays within the 7,680 MB budget; set the local model's extraction timeout and each source's `max_documents_per_run` so a capped run fits the task timeout. Re-`up` once if anything changed.

**Check:** no container above 90% of its limit; the numbers and the changes recorded in the report.

### 4. Daily check (days 1–21, about 5 minutes)
From the daily health summary, or the Infrastructure dashboard when it didn't arrive: every live source ran in the last 26 hours; documents fetched, published and failed per source; DLT depth; consumer lag back to 0 within an hour of the runs; price refresh current for the last NYSE session; container restarts; VM disk free and growth since yesterday; Mac swap; alerts fired, resolved and still open. Any red item gets an incident line in the report the same day (time, symptom, cause, whether it recovered without help).

**Check:** each day has its line in the report, including the days nothing happened.

### 5. Induced faults (week 2, one per day, never on a 1st–7th of the month)
1. Quit Ollama for an hour across a scheduled run, then start it.
2. Restart Docker Desktop.
3. Reboot the Mac.
4. Let the Mac sleep overnight (re-enable sleep for one night, then disable it again).
5. Stop Neo4j for two minutes while signals are flowing.

**Check:** after each fault, the next scheduled runs recover without help: cursors only move forward, failed documents are re-extracted, nothing new stays in the DLT, and an alert (or the summary) reported the fault.

### 6. Close (day 21)
Repeat the day-0 measurements, compute the criteria below, write `docs/soak-test-report.md`, add a VERIFIED entry (or a FLAG per failed criterion) to `DECISIONS.md`, and open a PR into `develop` with the report, `DECISIONS.md`, this spec moved to `specs/done/` if it passed, and its `TODO.md` row.

## Required tests

Checks run on the Mac, each falsifiable and recorded in the report:
- `check_mac_stays_awake_and_restarts_its_services_after_reboot` — step 1
- `check_no_document_is_lost` — every fetched document is published, not-a-signal, below threshold, or still pending retry; Postgres row count equals distinct `event_id` count and matches the Neo4j `Signal` count
- `check_each_live_source_succeeded_on_at_least_19_of_21_days_and_caught_up_after_each_miss`
- `check_cursors_only_moved_forward`
- `check_no_refreshed_ticker_missed_more_than_one_nyse_session`
- `check_the_month_universe_was_built_by_day_seven`
- `check_no_container_was_oom_killed_or_restarted_without_a_known_cause`
- `check_vm_memory_p95_stayed_under_85_percent_and_mac_swap_did_not_grow_day_over_day`
- `check_disk_growth_projects_under_70_percent_of_the_vm_disk_at_90_days`
- `check_every_induced_fault_alerted_and_recovered_without_help`
- `check_false_alerts_averaged_under_one_per_day`
- `check_week_three_extraction_p95_within_20_percent_of_week_one`
- `check_dlt_holds_no_unexplained_record`

## Definition of done

On the Mac, at step 6:

```bash
test -s docs/soak-test-report.md && grep -c '^| check_' docs/soak-test-report.md   # 13 rows, one per check
grep -c -E 'Soak test — (VERIFIED|FLAG)' DECISIONS.md                              # at least 1
git status --short                                                                 # no .env, no scratch files
```

Expected: the report exists with 13 check rows, each `pass` or `fail` with its evidence; at least one DECISIONS entry; the PR into `develop` is open with CI green. The run passes when every check passes.

## Notes

- Start the run so that day 1 of a month falls in week 1 or week 3, leaving week 2 free for the induced faults, and, if possible, so it spans a US market holiday (the price refresh should expect no bar).
- If a failure needs a code fix mid-run, restarting the clock is the owner's call; record the decision in the report.
