# Research input archive

**Status:** draft
**Blocked by:** user decision on disk budget (see Notes)
**Branch:** `feature/research-input-archive`

---

## Context

The universe and ownership builds download SEC archives, parse them and keep only the result:
- `services/backtesting/src/auspex_backtesting/universe/job.py` reads the SEC submissions and companyfacts archives from temporary storage and removes them after parsing.
- `ownership/form13f.py` parses each Form 13F data set ZIP in a temporary directory and stores the parsed panel with its URL and report metadata; the ZIP is deleted with the directory. Insider data sets are handled the same way.
- `ownership/job.py` replaces the share-count reference object on each run.

A stored panel can be re-read, but not rebuilt from the exact bytes it came from: SEC revises its bulk files, and the issuer mapping uses current and former names and current SIC codes. When a parser or mapping changes, an old and a new panel cannot be compared input for input.

Found by the consolidated audit of 2026-10-10 (finding C8; the audit file is in the project's `audit/` folder) and checked against `develop` at `d615504`. The audit rates it a design gap now and a blocker before research results are interpreted.

## What this builds

To be scoped. The direction from the audit: keep each downloaded source file content-addressed (SHA-256) in MinIO with its retrieval time and URL, and bind every derived snapshot (universe month, ownership panel, share-count reference) to a manifest of the input hashes and the code version that built it, so a rebuild with the network off gives the same bytes.

**What it gates:** a result is admissible (a run marked final, a holdout read, a promotion) only when every snapshot it reads carries an input manifest. `cross-sectional-portfolio-backtest` refuses to mark a run final otherwise. Builds made before this spec is done, including the first universe build on the stack machine, are disposable: usable in-sample and for measuring the disk this spec needs, never for an admissible result, and rebuilt with manifests once it is done.

## Out of scope

- Price snapshots (`specs/price-finality-and-split-availability.md`).
- Raw scraped documents, which `auspex-raw` already archives (invariant 13).

## Constraints

- Invariant 9: UTC retrieval times.
- No change to universe rules or registered hypotheses.

## Required tests

To be written when scoped.

## Definition of done

To be written when scoped.

## Notes

- **Decision needed before scoping:** keep the raw SEC files (one submissions and one companyfacts archive per build, plus every 13F and insider data set since 2013) or only canonical parsed tables with hashes of the files they came from. The first is byte-exact but costs several GB of disk on the stack machine per build; the second is small but cannot detect a parser bug in the parse itself. The size per build is measured in the first run (`specs/first-run-on-stack-machine.md`).
