# Golden Set Expansion

**Status:** blocked
**Blocked by:** `model-evaluation` — the local model must be selected (≥0.85 precision gate, DECISIONS.md CHOICE entry written) before gate records can be re-established for the expanded set under the chosen model.
**Branch:** `feature/golden-set-expansion`

---

## Context

The Phase 2 golden set is 50 documents covering a single disease area (DMD — dystrophin gene therapy). `score_extraction.py --model gpt-4o-mini-2024-07-18` produced precision=1.000 on this set at `prompt_version=v1.0`, `prefilter_version=v1.0`.

This is too narrow to trust Phase 4 findings across the full watchlist. The 8 watched companies span multiple gene targets and disease areas. A golden set that validates only DMD extraction does not detect model failures on other targets, and a gate record that passes on 50 DMD documents does not establish that the backfill model extracts reliably across the corpus it will actually process.

Both the API model and the chosen local model need gate records on the expanded set before the historical backfill starts.

## What this builds

An expanded golden set at `tests/fixtures/golden_set.jsonl` (extending the existing file):
- At least 150 documents total.
- At least 4 distinct gene targets represented (beyond DMD).
- At least 3 distinct source types.
- Hand-labelled `is_signal` (true/false) for every document. No unlabelled placeholders.
- Fields: `external_id`, `source_type`, `gene_target`, `is_signal`, `published_date`.

After committing the expanded fixture:
- `score_extraction.py --model <local_model_key>` — gate record written for the chosen backfill model at the expanded set's prompt and prefilter versions.
- `score_extraction.py --model gpt-4o-mini-2024-07-18` — gate record updated for the API model.

Both gate records must be present with `passed: true` before `historical-backfill` can start.

## Out of scope

Changes to `score_extraction.py`. Changes to the LLM extraction prompt (a prompt change requires a new `prompt_version` and invalidates all existing gate records). New fields on `ResearchSignalEvent`. This spec only extends the fixture and re-runs the existing scoring script.

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

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit/test_golden_set.py -q
```

Expected: 4 passed.

Then:
- `score_extraction.py --model <local_model_key>` completes at ≥0.85 precision; gate record committed to `config/models/scores/`.
- `score_extraction.py --model gpt-4o-mini-2024-07-18` completes; gate record file updated.
- Both gate record files committed.
- Precision scores on the expanded set for both models recorded in `DECISIONS.md`.

## Notes

The labelling effort is significant: ~100 additional documents, each requiring inspection and a binary label. Prioritise source types already in the MinIO archive (ClinicalTrials.gov, PubMed, bioRxiv) — documents are already fetched and can be re-read from `auspex-raw`. Query `signal_extraction_history` for the gene targets with the most in-window documents to prioritise which targets to label first.

If the local model scores below 0.85 on the expanded set after passing the DMD-only set, investigate whether the failure is gene-target-specific before concluding the model is unsuitable. A failure on a single gene target may be addressable via prompt tuning on a small in-context example — but that changes `prompt_version` and requires re-scoring all registered models.
