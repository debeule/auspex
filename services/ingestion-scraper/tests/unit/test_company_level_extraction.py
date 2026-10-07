import hashlib
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

from auspex_ingest.extraction_backend import BackendLLMExtractor
from auspex_ingest.extractor import _ExtractionResult
from auspex_ingest.models import EVENT_SCHEMA_VERSION, RawDocument

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts" / "extraction"
_T0 = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
_ENTRY = {"num_ctx": 8192, "temperature": 0, "seed": 42}


def _doc(canonical_id: str | None = None, content: str = "Topline data for SRP-9001") -> RawDocument:
    return RawDocument(
        schema_version="1.0",
        external_id="ext-001",
        canonical_id=canonical_id,
        source_type="edgar",
        source_url="https://example.com/doc/1",
        published_date=_T0,
        raw_content=content,
        content_sha256=hashlib.sha256(content.encode()).hexdigest(),
        retrieved_at=_T0,
    )


def _extractor(result: _ExtractionResult) -> BackendLLMExtractor:
    client = MagicMock()
    client.chat.completions.create.return_value = result
    return BackendLLMExtractor(
        client=client,
        model_id="test-model",
        entry=_ENTRY,
        schema_version=EVENT_SCHEMA_VERSION,
        prompt_version="v1.1",
        prompt_text="system prompt",
        now=lambda: _T0,
    )


def _signal(**fields: object) -> _ExtractionResult:
    return _ExtractionResult.model_validate({
        "is_signal": True,
        "title": "Sarepta reports topline results",
        "summary": "SRP-9001 met its primary endpoint",
        "directionality": "positive",
        "confidence_score": 0.9,
        **fields,
    })


def test_extracted_event_carries_event_type_company_and_program_identifiers():
    result = _signal(
        event_type="trial_readout",
        primary_company="Sarepta Therapeutics",
        program_identifiers=["SRP-9001", "delandistrogene moxeparvovec"],
        trial_ids=["NCT05096221"],
    )

    event = _extractor(result).extract(_doc(), prefilter_version="v1", raw_object_key="k")

    assert event is not None
    assert event.event_type == "trial_readout"
    assert event.primary_company == "Sarepta Therapeutics"
    assert event.program_identifiers == ["SRP-9001", "delandistrogene moxeparvovec"]
    assert event.trial_ids == ["NCT05096221"]


def test_unknown_event_type_from_model_is_recorded_as_other():
    result = _signal(event_type="topline readout!")

    event = _extractor(result).extract(_doc(), prefilter_version="v1", raw_object_key="k")

    assert event is not None
    assert event.event_type == "other"


def test_malformed_trial_ids_are_dropped_and_valid_ones_upper_cased():
    result = _signal(trial_ids=["nct05096221", "NCT123", "EudraCT 2020-001234-56", " NCT04281485 "])

    event = _extractor(result).extract(_doc(), prefilter_version="v1", raw_object_key="k")

    assert event is not None
    assert event.trial_ids == ["NCT05096221", "NCT04281485"]


def test_clinical_trial_document_always_lists_its_own_nct_id():
    result = _signal(trial_ids=[])

    event = _extractor(result).extract(
        _doc(canonical_id="nct:NCT06123456"), prefilter_version="v1", raw_object_key="k"
    )

    assert event is not None
    assert event.trial_ids == ["NCT06123456"]


def test_events_are_stamped_with_the_current_schema_version():
    event = _extractor(_signal()).extract(_doc(), prefilter_version="v1", raw_object_key="k")

    assert EVENT_SCHEMA_VERSION == "1.1"
    assert event is not None
    assert event.schema_version == EVENT_SCHEMA_VERSION


def test_prompt_v1_1_asks_for_every_new_field():
    prompt = (_PROMPT_DIR / "v1.1.txt").read_text()

    for field in ("event_type", "primary_company", "program_identifiers", "trial_ids"):
        assert f"**{field}**" in prompt, f"prompt v1.1 has no extraction rule for {field}"
    for event_type in _ExtractionResult.model_fields["event_type"].annotation.__args__:
        assert f"`{event_type}`" in prompt, f"prompt v1.1 does not define {event_type}"


def test_production_default_prompt_version_is_v1_1():
    from auspex_ingest import extraction_backend

    assert extraction_backend._DEFAULT_PROMPT_VERSION == "v1.1"
    assert (_PROMPT_DIR / "v1.1.txt").exists()
