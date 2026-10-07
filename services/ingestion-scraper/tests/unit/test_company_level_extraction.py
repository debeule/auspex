import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import get_args
from unittest.mock import MagicMock

import pytest
import yaml

from auspex_ingest.extraction_backend import (
    BackendLLMExtractor,
    GateNotPassedError,
    build_extractor_from_env,
)
from auspex_ingest.extractor import EventType, _ExtractionResult
from auspex_ingest.messaging import KafkaProducerClient
from auspex_ingest.models import EVENT_SCHEMA_VERSION, RawDocument, ResearchSignalEvent
from auspex_ingest.prefilter import PREFILTER_VERSION

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


@pytest.mark.parametrize("event_type", get_args(EventType))
def test_every_documented_event_type_is_kept_as_extracted(event_type):
    event = _extractor(_signal(event_type=event_type)).extract(
        _doc(), prefilter_version="v1", raw_object_key="k"
    )

    assert event is not None
    assert event.event_type == event_type


def test_missing_company_level_values_default_to_none_and_empty_lists():
    event = _extractor(_signal()).extract(_doc(), prefilter_version="v1", raw_object_key="k")

    assert event is not None
    assert event.event_type == "other"
    assert event.primary_company is None
    assert event.program_identifiers == []
    assert event.trial_ids == []


def test_null_identifier_lists_from_model_are_treated_as_empty():
    result = _signal(program_identifiers=None, trial_ids=None, event_type=None)

    event = _extractor(result).extract(_doc(), prefilter_version="v1", raw_object_key="k")

    assert event is not None
    assert event.program_identifiers == []
    assert event.trial_ids == []
    assert event.event_type == "other"


def test_blank_primary_company_is_recorded_as_none():
    event = _extractor(_signal(primary_company="   ")).extract(
        _doc(), prefilter_version="v1", raw_object_key="k"
    )

    assert event is not None
    assert event.primary_company is None


def test_own_nct_id_is_not_duplicated_when_the_model_also_returns_it():
    result = _signal(trial_ids=["nct06123456", "NCT05096221"])

    event = _extractor(result).extract(
        _doc(canonical_id="nct:NCT06123456"), prefilter_version="v1", raw_object_key="k"
    )

    assert event is not None
    assert event.trial_ids == ["NCT06123456", "NCT05096221"]


def test_non_trial_canonical_id_adds_no_trial():
    event = _extractor(_signal()).extract(
        _doc(canonical_id="edgar:0000950170-23-029354"), prefilter_version="v1", raw_object_key="k"
    )

    assert event is not None
    assert event.trial_ids == []


def test_kafka_payload_round_trips_every_company_level_field():
    event = _extractor(
        _signal(
            event_type="complete_response_letter",
            primary_company="Sarepta Therapeutics",
            program_identifiers=["SRP-9001"],
            trial_ids=["NCT05096221"],
        )
    ).extract(_doc(), prefilter_version="v1", raw_object_key="k")
    assert event is not None
    producer = MagicMock()

    KafkaProducerClient(producer, raw_topic="raw", signals_topic="signals").publish_signal(event)

    kwargs = producer.produce.call_args.kwargs
    payload = json.loads(kwargs["value"])
    assert kwargs["headers"] == {"schema_version": "1.1"}
    assert payload["event_type"] == "complete_response_letter"
    assert payload["primary_company"] == "Sarepta Therapeutics"
    assert payload["program_identifiers"] == ["SRP-9001"]
    assert payload["trial_ids"] == ["NCT05096221"]
    assert ResearchSignalEvent.model_validate_json(kwargs["value"]) == event


def test_production_extractor_stamps_the_current_schema_version_by_default(tmp_path):
    registry, scores = _registry_with_gate(tmp_path, "v1.1")
    extractor = build_extractor_from_env(_env(registry, scores))
    extractor._client = MagicMock()
    extractor._client.chat.completions.create.return_value = _signal()

    event = extractor.extract(_doc(), prefilter_version=PREFILTER_VERSION, raw_object_key="k")

    assert event is not None
    assert event.schema_version == "1.1"
    assert event.prompt_version == "v1.1"


def test_production_refuses_to_start_with_only_a_v1_0_gate_record(tmp_path):
    registry, scores = _registry_with_gate(tmp_path, "v1.0")

    with pytest.raises(GateNotPassedError, match="v1.1"):
        build_extractor_from_env(_env(registry, scores))


_MODEL = "gpt-4o-mini-2024-07-18"


def _registry_with_gate(tmp_path: Path, prompt_version: str) -> tuple[Path, Path]:
    registry = tmp_path / "registry.yaml"
    registry.write_text(yaml.safe_dump({"models": {_MODEL: {
        "backend": "api",
        "cutoff_date": "2023-10-01",
        "cutoff_source": "https://example.com",
        "num_ctx": 8192,
        "timeout": 30,
        "temperature": 0,
        "seed": 42,
        "structured_output_mode": "JSON",
    }}}))
    scores = tmp_path / "scores"
    scores.mkdir()
    (scores / f"{_MODEL}.json").write_text(json.dumps({
        "model_id": _MODEL,
        "prompt_version": prompt_version,
        "prefilter_version": PREFILTER_VERSION,
        "precision": 0.9,
        "passed": True,
    }))
    return registry, scores


def _env(registry: Path, scores: Path) -> dict[str, str]:
    return {
        "EXTRACTION_MODEL": _MODEL,
        "EXTRACTION_API_KEY": "test-key",
        "EXTRACTION_REGISTRY_PATH": str(registry),
        "EXTRACTION_SCORES_DIR": str(scores),
    }


def test_legacy_extractor_maps_company_level_fields_the_same_way():
    from auspex_ingest.extractor import LLMExtractor

    client = MagicMock()
    client.chat.completions.create.return_value = _signal(
        event_type="clinical_hold", primary_company="Rocket", trial_ids=["bad"]
    )
    extractor = LLMExtractor(
        client=client, model="m", schema_version=EVENT_SCHEMA_VERSION, prompt_version="v1.1"
    )

    event = extractor.extract(
        _doc(canonical_id="nct:NCT06123456"), prefilter_version="v1", raw_object_key="k"
    )

    assert event is not None
    assert event.event_type == "clinical_hold"
    assert event.primary_company == "Rocket"
    assert event.trial_ids == ["NCT06123456"]
