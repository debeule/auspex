# Golden Set Expansion

**Status:** blocked
**Blocked by:** `model-evaluation` — the local model must be selected (≥0.85 precision gate, DECISIONS.md CHOICE entry written) before gate records can be re-established for the expanded set under the chosen model.
**Branch:** `feature/golden-set-expansion`

---

## Context

The Phase 2 golden set is 50 documents covering a single disease area (DMD — dystrophin gene therapy). No model has a gate record against it yet: the earlier `gpt-4o-mini-2024-07-18` record was written by hand, not by `score_extraction.py`, and was removed.

This is too narrow to trust Phase 4 findings across the full watchlist. The 8 watched companies span multiple gene targets and disease areas. A golden set that validates only DMD extraction does not detect model failures on other targets, and a gate record that passes on 50 DMD documents does not establish that the backfill model extracts reliably across the corpus it will actually process.

Both the API model and the chosen local model need gate records on the expanded set before the historical backfill starts.

## What this builds

An expanded golden set at `tests/fixtures/golden_set.jsonl` (extending the existing file):
- At least 150 documents total.
- At least 4 distinct gene targets represented (beyond DMD).
- At least 3 distinct source types.
- Hand-labelled `is_signal` (true/false) for every document. No unlabelled placeholders.
- Enough documents per live source that the chosen model extracts at least 30 signals from each, so every source can be calibrated (see below).
- Fields: `external_id`, `source_type`, `gene_target`, `is_signal`, `published_date`.

After committing the expanded fixture:
- `score_extraction.py --model <local_model_key>` — gate record written for the chosen backfill model at the expanded set's prompt and prefilter versions.
- `score_extraction.py --model gpt-4o-mini-2024-07-18` — gate record updated for the API model.

Both gate records must be present with `passed: true` before `historical-backfill` can start.

### Confidence calibration and publish thresholds

`min_confidence_to_publish` ships at 0.0 (off) because requirements §11.1 forbids a threshold the score's calibration has not measured. The user decided on 2026-10-09 that this must be corrected before launch, so this spec measures it:

- `score_extraction.py --calibrate` scores the chosen local model's `confidence_score` against the hand labels: for each `source_type` in `sources.yaml` that is not a fixture source, it bins the extracted signals by confidence (5 equal-width bins on [0, 1]) and reports per-bin count and precision (share labelled `is_signal: true`).
- The calibrated threshold for a source is the lowest bin edge from which every higher bin meets the 0.85 gate precision. If every bin meets it, the threshold is 0.0, now recorded on evidence instead of by default.
- A source with fewer than 30 extracted signals in the set is reported `uncalibrated`, not given a threshold.
- The result is written to `config/models/scores/calibration.json` (model key, `prompt_version`, `prefilter_version`, per source: bins, threshold or `uncalibrated`), and each calibrated threshold is set as `min_confidence_to_publish` on that source's `sources.yaml` entry in the same commit.
- A model or `prompt_version` change makes the calibration stale, like a gate record.

## Out of scope

Changes to `score_extraction.py` other than the `--calibrate` mode above. Changes to the LLM extraction prompt (a prompt change requires a new `prompt_version` and invalidates all existing gate records). New fields on `ResearchSignalEvent`. This spec only extends the fixture and re-runs the existing scoring script.

## Constraints

- Documents must come from real archived sources (MinIO raw archive or re-fetched and hand-inspected). No synthetic documents — labels must reflect actual extraction outcomes.
- Documents from after the local model's knowledge cutoff must not be included if they fall within the backfill window. The golden set tests extraction quality, not leakage.
- `pytest-socket --disable-socket` unchanged — the fixture is static; no live calls in test.

## Required tests

Static validation of the expanded fixture in `tests/unit/test_golden_set.py`:

- `test_golden_set_minimum_document_count` — at least 150 documents; fails explicitly rather than producing misleading metrics at lower counts
- `test_golden_set_spans_required_gene_targets` — at least 4 distinct gene target values present
- `test_golden_set_spans_required_source_types` — at least 3 distinct source types
- `test_golden_set_labels_complete` — every document has a non-null `is_signal` field; no unlabelled entries

Calibration in `tests/unit/test_confidence_calibration.py`:

- `test_calibration_bins_confidence_against_hand_labels` — synthetic scored set; per-bin counts and precision match hand-computed values
- `test_threshold_is_lowest_bin_edge_from_which_all_higher_bins_meet_target_precision` — a non-monotonic middle bin below 0.85 raises the threshold above it
- `test_threshold_is_zero_when_every_bin_meets_target_precision`
- `test_source_with_fewer_than_thirty_extracted_signals_is_uncalibrated`
- `test_every_live_source_has_a_current_calibration_matching_its_publish_threshold` — reads `sources.yaml`, `calibration.json` and `registry.yaml`: every non-fixture source has an entry for the active model and `prompt_version`, and its `min_confidence_to_publish` equals the recorded threshold. Write it red, then commit it together with `calibration.json` and the `sources.yaml` thresholds from the calibration run, never before: the unit suite stays green on every commit, and from then on a model or prompt change without a new calibration turns it red. No skip marker.

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit/test_golden_set.py -q
cd services/ingestion-scraper && uv run pytest tests/unit/test_confidence_calibration.py -q
```

Expected: 4 passed, then 5 passed (the fifth calibration test lands with the calibration run below).

Then:
- `score_extraction.py --model <local_model_key>` completes at ≥0.85 precision; gate record committed to `config/models/scores/`.
- `score_extraction.py --model gpt-4o-mini-2024-07-18` completes; gate record file updated.
- Both gate record files committed.
- Precision scores on the expanded set for both models recorded in `DECISIONS.md`.
- `score_extraction.py --calibrate --model <local_model_key>` run on the expanded set; `calibration.json` and the resulting `sources.yaml` thresholds committed together; per-source thresholds and any `uncalibrated` source recorded in `DECISIONS.md`.

## Notes

The labelling effort is significant: ~100 additional documents, each requiring inspection and a binary label. Prioritise source types already in the MinIO archive (ClinicalTrials.gov, PubMed, bioRxiv) — documents are already fetched and can be re-read from `auspex-raw`. Query `signal_extraction_history` for the gene targets with the most in-window documents to prioritise which targets to label first.

If the local model scores below 0.85 on the expanded set after passing the DMD-only set, investigate whether the failure is gene-target-specific before concluding the model is unsuitable. A failure on a single gene target may be addressable via prompt tuning on a small in-context example — but that changes `prompt_version` and requires re-scoring all registered models.
