# Research input archive

**Status:** ready
**Blocked by:** —
**Branch:** `feature/research-input-archive`

---

## Context

The universe and ownership builds download SEC archives, parse them and keep only the result:
- `services/backtesting/src/auspex_backtesting/universe/job.py` (`SecBulkSource.load`) downloads `submissions.zip` and `companyfacts.zip` through `universe/sec_bulk.py` into a temporary directory and deletes them after parsing. `read_submissions` reads the first 4 KB of every `CIK##########.json` member to test its SIC code and parses the matching members in full (every member for `us_small_mid`, whose `sic_codes` is empty); `read_share_counts` parses the companyfacts members of the chosen CIKs. `universe/sec_index.py` fetches one `-index.htm` page per delisted company.
- `ownership/job.py` downloads `submissions.zip` again for the issuer directory (`ownership/issuers.py` reads only the first 4 KB of each member with a SIC code) and `companyfacts.zip` again for the share-count reference, which it replaces on each run (`SHARES_OUTSTANDING_KEY`).
- `ownership/form13f.py` and `ownership/insider.py` parse each Form 13F and Form 3/4/5 data set ZIP in a temporary directory; the ZIP is deleted with the directory. `insider.py` also reads EDGAR quarterly `form.idx` files (offerings) and daily `form.YYYYMMDD.idx` files plus each universe Form 4 XML (daily fill).
- `filings/archive.py` keeps the cut Item 1A section of each 10-K under `filings/item1a/` and drops the filing itself. It fetches the filing's `-index.htm` page and primary document through its `HttpSource`.
- Every SEC request in `ownership/` and `filings/` goes through an `HttpSource`-shaped client (`get(url) -> bytes`, `download(url, dest) -> Path`; `ownership/sec_client.py`, `catalysts/fetch.py`). `universe/sec_bulk.download` and `universe/sec_index.py` call `urllib` themselves.
- The portfolio verdict already refuses a final run without manifests: `portfolio/verdict.py` defines `InputManifests.missing(keys)`, `NoInputManifests` (every key missing) and `InputsNotPinnedError`; `PortfolioBacktest.input_keys()` lists every universe and score snapshot a run reads.

A stored panel can be re-read, but not rebuilt from the exact bytes it came from: SEC revises its bulk files nightly, and the issuer mapping uses current and former names and current SIC codes. When a parser or mapping changes, an old and a new panel cannot be compared input for input.

Found by the consolidated audit of 2026-10-10 (finding C8; the audit file is in the project's `audit/` folder). The audit rates it a design gap now and a blocker before research results are interpreted. What to keep was decided on 2026-10-17 (`DECISIONS.md`): the bytes each parser read rather than every bulk ZIP whole, and each 10-K behind an Item 1A section, with no size cap.

## What this builds

When done, every universe month, ownership panel, share-count reference and score snapshot carries an input manifest naming the exact bytes it was built from, those bytes are in MinIO, and the snapshot can be rebuilt with the network off to the same content. A final portfolio run is refused unless every snapshot it reads has a manifest.

1. **`SourceArchive`** (`auspex_backtesting.archive`): a content-addressed blob store under `archive/blobs/<sha256[:2]>/<sha256>` in `auspex-prices`, gzip with `mtime=0`. A blob is written once; putting an existing hash writes nothing. Each retrieval is recorded with its URL, retrieval time (UTC) and SHA-256 of the whole response.
2. **What is kept, per source:**
   - Data set ZIPs (Form 13F, Form 3/4/5), EDGAR `form.idx` files, Form 4 XMLs, `-index.htm` pages and the 10-K primary documents `filings/archive.py` cuts Item 1A from: the whole response as one blob. These are already compressed or small, and the data sets never change after publication, so each is stored once.
   - `submissions.zip` and `companyfacts.zip`: not the ZIP. For each member a parser opened, the bytes it read: the whole member when parsed in full, the first 4 KB when only the header was read. Each is a blob, so a member that did not change since the last build costs nothing. Next to them, one **member index** per downloaded ZIP: every member name with the SHA-256 of the whole member, and for members read, the blob hash and the length read. The member index is itself a blob (Parquet, zstd).
3. **`ArchivingSecSource`**: wraps the SEC client so every `get` and `download` is archived before its bytes reach a parser (the archive is written first, as invariant 13 does for raw documents). `sec_bulk` and `sec_index` move onto the shared client so nothing reaches SEC around it, and the filing panel build (`filings/job.py`) passes it to `FilingSectionArchive`. Bulk ZIP readers open members through a recorder that notes each member and how many bytes were read.
4. **`InputManifest`** written next to each derived object as `<key>.manifest.json`: the snapshot key and the SHA-256 of its canonical content (below), `code_version`, `built_at` (UTC), and its inputs. An input is either a retrieval (`url`, `retrieved_at`, `sha256`, `blob`, or for a bulk ZIP its `member_index` blob) or another snapshot (`key`, its content hash, its manifest's SHA-256). Score snapshots name the universe snapshot, ownership panels, filing sections and other snapshots they read. A filing section's manifest names its index page and primary document blobs, so the section cut can be rebuilt too. Price snapshots and short-interest snapshots are listed by key and content hash only (see Out of scope).
   - `code_version` is the SHA-256 over the sorted paths and bytes of the installed `auspex_backtesting` package's `.py` files plus the rules or hypothesis file the build used. No git metadata is needed in the image.
   - The canonical content hash is over the snapshot's rows sorted by its natural key and its stored metadata, serialized deterministically, not over the Parquet file bytes (Parquet footers carry the writer version).
5. **`ManifestStore`** implements `InputManifests.missing(keys)`: a key is missing when it has no manifest, when the manifest's content hash does not match the stored snapshot, or when any input it names (blob, member index or snapshot manifest) is absent. `scripts/run_portfolio_backtest.py` and every other `PortfolioEvaluation` caller use it in place of `NoInputManifests`.
6. **`OfflineRebuild`**: given a manifest, re-runs the build with a `ReplaySecSource` that serves only the archived retrievals and raises `NotArchivedError` on any other URL, and reconstructs each bulk ZIP from its member index (members not read are absent; reading past an archived header raises). It reports `identical` when the rebuilt content hash equals the manifest's, otherwise `differs` with the first differing rows. The same `code_version` must give `identical`.
7. **Rebuilding disposable snapshots.** A snapshot without a manifest is disposable. A build that finds one rebuilds and replaces it, even where the store is otherwise write-once (`ownership/store.py` raises `PanelExistsError`); a snapshot that has a manifest stays write-once.
8. **Size, reported, not capped.** Each build logs the bytes it added to `archive/`. There is no budget variable, alert or stop: the MinIO volume's size already shows on the Infrastructure dashboard (`auspex_volume_bytes`). `docker/README.md`'s disk budget table gains the archive's row (store, expected growth, bounded by nothing but what the builds read).

## Out of scope

- Price snapshots and split histories (`specs/done/price-finality-and-split-availability.md` owns their finality). Manifests reference them by key and content hash only.
- FINRA short interest: its snapshots are the API response already. Referenced by key and content hash only.
- Raw scraped documents, which `auspex-raw` already archives (invariant 13), and catalyst documents, which `catalysts/fetch.py`'s `DocumentCache` already keeps.
- A size cap, a budget alert and pruning. The user allows up to 150 GB on the stack machine and needs no guards (2026-10-17); the archive keeps everything the builds read.
- Any change to universe rules, registered hypotheses or what a build selects.

## Constraints

- Invariant 6: any new URLs live in `.env` / `.env.example`, not in source.
- Invariant 9: retrieval and build times are UTC, including in object keys.
- Invariant 10: blobs are keyed by content hash and manifests by snapshot key; rewriting either with the same content is a no-op.
- Invariant 13, applied here: an SEC response is archived before any parser reads it. A failed archive write fails the build; it never parses unarchived bytes.
- SEC rate limits are unchanged (known trap): archiving adds no request. Replay makes none.
- Builds must still run within price-service's memory limit: blobs and member indexes are streamed, not held whole in memory.
- MinIO-touching code gets a LocalStack integration test in CI.

## Required tests

Unit (`services/backtesting/tests/unit/test_source_archive.py`, `test_input_manifest.py`, `test_offline_rebuild.py`):
- `test_blob_is_stored_once_per_content_hash` — putting the same bytes twice writes one object
- `test_blob_is_gzip_with_zero_mtime` — the stored bytes are identical across two puts on different days
- `test_retrieval_is_archived_before_the_parser_reads_it` — a failing archive write raises and the parser is never called
- `test_retrieval_records_url_utc_time_and_sha256`
- `test_filing_section_manifest_names_its_index_page_and_primary_document_blobs`
- `test_offline_rebuild_of_a_filing_section_is_identical` — a fake 10-K archived, the section cut again offline, same content hash
- `test_bulk_zip_keeps_only_members_a_parser_read` — a fake ZIP with three members, one read in full and one header-only, archives two blobs and no third
- `test_header_only_read_archives_exactly_the_bytes_read` — the blob is the first 4 KB, not the member
- `test_member_index_lists_every_member_with_its_whole_hash` — unread members appear with their hash and no blob
- `test_unchanged_member_adds_no_bytes_on_the_next_build` — two builds whose ZIPs differ in one member add one member blob and one index
- `test_universe_and_ownership_reach_sec_only_through_the_archiving_source` — with the archiving source stubbed, `SecBulkSource` and `InstanceDocuments` make no `urllib` call
- `test_manifest_names_every_retrieval_the_build_made`
- `test_score_manifest_references_its_input_snapshots_by_content_hash`
- `test_code_version_changes_when_a_package_file_changes` — and stays equal when nothing changes
- `test_content_hash_ignores_parquet_writer_metadata` — the same rows written by two writer versions hash the same
- `test_missing_reports_a_snapshot_without_manifest`
- `test_missing_reports_a_manifest_whose_content_hash_no_longer_matches`
- `test_missing_reports_a_manifest_whose_input_blob_is_gone`
- `test_final_run_is_refused_with_the_manifest_store_until_every_input_is_pinned` — `PortfolioEvaluation(..., final=True)` raises `InputsNotPinnedError`, then passes once manifests are written
- `test_replay_source_raises_on_an_unarchived_url`
- `test_replay_raises_when_a_parser_reads_past_an_archived_header`
- `test_offline_rebuild_of_a_universe_month_is_identical` — fake bulk ZIPs, build, rebuild offline, same content hash
- `test_offline_rebuild_reports_differs_after_a_parser_change` — a patched parser gives `differs` with the first differing row
- `test_disposable_snapshot_is_rebuilt_and_replaced`
- `test_snapshot_with_manifest_stays_write_once`

Integration (`services/backtesting/tests/integration/test_source_archive_storage.py`, LocalStack):
- `test_blob_member_index_and_manifest_round_trip_through_s3`
- `test_offline_rebuild_reads_only_from_s3` — sockets disabled except to LocalStack

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_source_archive.py tests/unit/test_input_manifest.py tests/unit/test_offline_rebuild.py -q
cd services/backtesting && uv run pytest tests/unit -q
cd services/backtesting && uv run ruff check . && uv run mypy src
```

Expected: the 25 archive tests pass, the backtesting unit suite stays green, ruff and mypy are clean. The 2 integration tests pass in CI.

Then on the stack machine, add to `specs/first-run-on-stack-machine.md` step 8: after the first universe and ownership builds, record in `DECISIONS.md` the bytes each build added and the archive total, and run `OfflineRebuild` on one universe month and one 13F panel (both `identical`).

## Notes

- **What is kept (decided 2026-10-17, `DECISIONS.md`):** the bytes each parser read and the raw 10-Ks, with no cap. The user allows up to 150 GB on the stack machine but not waste, and needs no guards. The alternatives were parsed tables plus source hashes only (under 1 GB, but a parser bug cannot be found by rebuilding) and every bulk ZIP whole (40–100 GB a year, mostly bytes no parser reads).
- **Size estimate, to be replaced by the first-run measurement.** Data set ZIPs from 2013, from SEC's listings on 2026-10-17: Form 13F 54 files, 2.9 GB (about 0.36 GB a year added); Form 3/4/5 55 files, 0.56 GB (about 40 MB a year). The bulk pair is an estimate, since the cloud sessions cannot reach sec.gov: about 1.5 GB (`submissions.zip`) and 1.3 GB (`companyfacts.zip`) compressed. `us_small_mid` parses every submissions member, so the first build keeps close to the whole pair, about 3 GB. After that only changed members are added, plus a member index of about 30 MB per downloaded submissions ZIP. The raw 10-Ks add an estimated 10–15 GB gzipped for both universes from 2014 (about 1–1.5 GB a year). Year one is therefore about 20–25 GB and later years about 6–8 GB, about 50 GB after five years. The nightly backup mirrors the archive into `BACKUP_HOST_DIR`, so it takes its size twice on the Mac.
- Builds made before this spec is done, including a first universe build on the stack machine, are disposable: usable in-sample and for measuring disk, never for an admissible result, and rebuilt with manifests by item 7.
