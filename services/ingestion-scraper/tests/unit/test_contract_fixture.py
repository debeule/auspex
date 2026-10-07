"""Generates the Java contract fixture; re-run whenever the Python model changes.

    cd services/ingestion-scraper && uv run pytest tests/unit/test_contract_fixture.py -v

Writes services/core-hub/src/test/resources/contract/signal_event_v1.json, which
ResearchSignalEventTest reads to verify Java deserialization of every field.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from auspex_ingest.identity import compute_event_id, compute_extraction_id
from auspex_ingest.models import EVENT_SCHEMA_VERSION, ResearchSignalEvent

_UTC = UTC
_T0 = datetime(2024, 6, 15, 12, 0, 0, tzinfo=_UTC)
_SCHEMA = EVENT_SCHEMA_VERSION
_PROMPT = "v1"
_PREFILTER = "v1"
_MODEL = "gpt-4o"
_CANONICAL_ID = "doi:10.1101/2024.06.01.600001"

_CONTRACT_PATH = (
    Path(__file__).resolve().parents[4]
    / "services/core-hub/src/test/resources/contract/signal_event_v1.json"
)


def _make_fixture() -> ResearchSignalEvent:
    event_id = compute_event_id(_CANONICAL_ID, "biorxiv", "ext-contract-001")
    extraction_id = compute_extraction_id(event_id, _SCHEMA, _PROMPT, _PREFILTER, _MODEL)
    return ResearchSignalEvent(
        schema_version=_SCHEMA,
        event_id=event_id,
        extraction_id=extraction_id,
        external_id="ext-contract-001",
        canonical_id=_CANONICAL_ID,
        raw_object_key="raw/biorxiv/ext-contract-001/20240615T120000Z-abcdef12.json",
        source_type="biorxiv",
        source_url="https://biorxiv.org/content/10.1101/2024.06.01.600001",
        published_date=_T0,
        published_date_field="date",
        ingested_at=_T0,
        title="CRISPR base editing of BCL11A in sickle cell disease",
        raw_text_snippet="BCL11A base editing of haematopoietic stem cells corrects sickle cell...",
        gene_targets=["BCL11A", "HBB"],
        mechanisms=["base editing", "CRISPR"],
        companies_mentioned=["Beam Therapeutics"],
        summary="BCL11A base editing shows efficacy in sickle cell disease model",
        directionality="positive",
        confidence_score=0.92,
        event_type="preclinical_data",
        primary_company="Beam Therapeutics",
        program_identifiers=["BEAM-101"],
        trial_ids=["NCT05456880"],
        prompt_version=_PROMPT,
        prefilter_version=_PREFILTER,
        extraction_model=_MODEL,
    )


def test_generate_contract_fixture():
    event = _make_fixture()
    payload = json.loads(event.model_dump_json())

    # sanity: all required fields present
    assert payload["schema_version"] == _SCHEMA
    assert payload["event_id"] is not None
    assert payload["extraction_id"] is not None
    assert payload["confidence_score"] == 0.92
    assert payload["gene_targets"] == ["BCL11A", "HBB"]
    assert payload["event_type"] == "preclinical_data"
    assert payload["primary_company"] == "Beam Therapeutics"
    assert payload["program_identifiers"] == ["BEAM-101"]
    assert payload["trial_ids"] == ["NCT05456880"]
    assert payload["published_date"].endswith("Z")
    assert payload["ingested_at"].endswith("Z")

    _CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONTRACT_PATH.write_text(json.dumps(payload, indent=2))
    print(f"\nWrote contract fixture → {_CONTRACT_PATH}")
