import json
import os
from pathlib import Path

import pytest

from auspex_ingest.extraction_backend import (
    ConfigurationError,
    ContextLengthError,
    GateNotPassedError,
    LLMExtractorFactory,
)
from auspex_ingest.models import RawDocument
from auspex_ingest.pipeline import IngestionPipeline
from auspex_ingest.prefilter import Prefilter

_VALID_API_ENTRY = {
    "gpt-4o-mini-2024-07-18": {
        "backend": "api",
        "cutoff_date": "2023-10-01",
        "cutoff_source": "https://openai.com/model-cards/gpt-4o-mini",
        "num_ctx": 8192,
        "timeout": 30,
        "temperature": 0,
        "seed": 42,
        "structured_output_mode": "JSON",
    }
}

_VALID_LOCAL_ENTRY = {
    "gemma3:27b@sha256:abc123": {
        "backend": "local",
        "cutoff_date": "2024-06-01",
        "cutoff_source": "https://ollama.com/library/gemma3",
        "num_ctx": 4096,
        "timeout": 120,
        "temperature": 0,
        "seed": 0,
        "structured_output_mode": "JSON",
        "digest": "gemma3:27b@sha256:abc123",
    }
}

_PASSING_SCORE = {
    "model_id": "gpt-4o-mini-2024-07-18",
    "prompt_version": "v1",
    "prefilter_version": "v1",
    "precision": 1.0,
    "passed": True,
    "scored_at": "2024-01-01T00:00:00Z",
}


def _make_registry_file(tmp_path: Path, entries: dict) -> Path:
    import yaml
    f = tmp_path / "registry.yaml"
    f.write_text(yaml.dump({"models": entries}))
    return f


def _make_score_file(scores_dir: Path, score: dict) -> Path:
    scores_dir.mkdir(parents=True, exist_ok=True)
    f = scores_dir / f"{score['model_id']}.json"
    f.write_text(json.dumps(score))
    return f


def _make_raw(content: str = "BCL11A gene target CRISPR editing trial") -> RawDocument:
    import hashlib
    from datetime import UTC, datetime
    sha = hashlib.sha256(content.encode()).hexdigest()
    return RawDocument(
        schema_version="1.0",
        external_id="ext-001",
        source_type="biorxiv",
        source_url="https://example.com/doc/1",
        published_date=datetime(2024, 1, 1, tzinfo=UTC),
        raw_content=content,
        content_sha256=sha,
        retrieved_at=datetime(2024, 1, 1, tzinfo=UTC),
    )


def _make_factory(
    tmp_path: Path,
    *,
    model_id: str = "gpt-4o-mini-2024-07-18",
    registry_entries: dict | None = None,
    score: dict | None = None,
    prompt_version: str = "v1",
    prefilter_version: str = "v1",
    model_info_fn=None,
    env_overrides: dict | None = None,
) -> LLMExtractorFactory:
    if registry_entries is None:
        registry_entries = _VALID_API_ENTRY
    if score is None:
        score = _PASSING_SCORE

    registry_path = _make_registry_file(tmp_path, registry_entries)
    scores_dir = tmp_path / "scores"
    _make_score_file(scores_dir, score)

    env = {k: v for k, v in (env_overrides or {}).items()}
    env.setdefault("EXTRACTION_MODEL", model_id)
    env.setdefault("EXTRACTION_API_KEY", "test-key")

    return LLMExtractorFactory(
        registry_path=registry_path,
        scores_dir=scores_dir,
        model_id=env["EXTRACTION_MODEL"],
        base_url=env.get("EXTRACTION_BASE_URL"),
        api_key=env.get("EXTRACTION_API_KEY"),
        prompt_version=prompt_version,
        prefilter_version=prefilter_version,
        model_info_fn=model_info_fn,
    )


def test_extraction_base_url_is_read_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("EXTRACTION_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("EXTRACTION_MODEL", "gpt-4o-mini-2024-07-18")
    monkeypatch.setenv("EXTRACTION_API_KEY", "test-key")

    registry_path = _make_registry_file(tmp_path, _VALID_API_ENTRY)
    scores_dir = tmp_path / "scores"
    _make_score_file(scores_dir, _PASSING_SCORE)

    factory = LLMExtractorFactory(
        registry_path=registry_path,
        scores_dir=scores_dir,
        model_id=os.environ["EXTRACTION_MODEL"],
        base_url=os.environ.get("EXTRACTION_BASE_URL"),
        api_key=os.environ.get("EXTRACTION_API_KEY"),
        prompt_version="v1",
        prefilter_version="v1",
    )
    assert factory.base_url == "http://localhost:11434/v1"


def test_extraction_base_url_defaults_to_openai_when_absent(tmp_path, monkeypatch):
    monkeypatch.delenv("EXTRACTION_BASE_URL", raising=False)

    registry_path = _make_registry_file(tmp_path, _VALID_API_ENTRY)
    scores_dir = tmp_path / "scores"
    _make_score_file(scores_dir, _PASSING_SCORE)

    factory = LLMExtractorFactory(
        registry_path=registry_path,
        scores_dir=scores_dir,
        model_id="gpt-4o-mini-2024-07-18",
        base_url=None,
        api_key="test-key",
        prompt_version="v1",
        prefilter_version="v1",
    )
    assert factory.base_url is None


def test_moving_alias_rejected_at_startup(tmp_path):
    registry_path = _make_registry_file(tmp_path, _VALID_API_ENTRY)
    scores_dir = tmp_path / "scores"
    _make_score_file(scores_dir, _PASSING_SCORE)

    with pytest.raises(ConfigurationError, match="gpt-4o-mini"):
        LLMExtractorFactory(
            registry_path=registry_path,
            scores_dir=scores_dir,
            model_id="gpt-4o-mini",
            base_url=None,
            api_key="test-key",
            prompt_version="v1",
            prefilter_version="v1",
        )


def test_unknown_model_fails_loudly_at_startup(tmp_path):
    registry_path = _make_registry_file(tmp_path, _VALID_API_ENTRY)
    scores_dir = tmp_path / "scores"
    _make_score_file(scores_dir, _PASSING_SCORE)

    with pytest.raises(ConfigurationError, match="gpt-x-9999"):
        LLMExtractorFactory(
            registry_path=registry_path,
            scores_dir=scores_dir,
            model_id="gpt-x-9999",
            base_url=None,
            api_key="test-key",
            prompt_version="v1",
            prefilter_version="v1",
        )


def test_registry_entry_missing_cutoff_source_is_rejected(tmp_path):
    import yaml
    bad_entry = {
        "bad-model": {
            "backend": "api",
            "cutoff_date": "2023-10-01",
            # cutoff_source missing
            "num_ctx": 8192,
            "timeout": 30,
            "temperature": 0,
            "seed": 42,
            "structured_output_mode": "JSON",
        }
    }
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(yaml.dump({"models": bad_entry}))
    scores_dir = tmp_path / "scores"
    scores_dir.mkdir()

    with pytest.raises(ConfigurationError, match="cutoff_source"):
        LLMExtractorFactory(
            registry_path=registry_path,
            scores_dir=scores_dir,
            model_id="bad-model",
            base_url=None,
            api_key="test-key",
            prompt_version="v1",
            prefilter_version="v1",
        )


def test_registry_entry_missing_digest_is_rejected_for_local_backend(tmp_path):
    import yaml
    bad_local = {
        "gemma3:27b": {
            "backend": "local",
            "cutoff_date": "2024-06-01",
            "cutoff_source": "https://ollama.com/library/gemma3",
            "num_ctx": 4096,
            "timeout": 120,
            "temperature": 0,
            "seed": 0,
            "structured_output_mode": "JSON",
            # digest missing
        }
    }
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(yaml.dump({"models": bad_local}))
    scores_dir = tmp_path / "scores"
    _make_score_file(scores_dir, {**_PASSING_SCORE, "model_id": "gemma3:27b"})

    with pytest.raises(ConfigurationError, match="digest"):
        LLMExtractorFactory(
            registry_path=registry_path,
            scores_dir=scores_dir,
            model_id="gemma3:27b",
            base_url=None,
            api_key="test-key",
            prompt_version="v1",
            prefilter_version="v1",
        )


def test_registry_entry_missing_num_ctx_is_rejected(tmp_path):
    import yaml
    bad_entry = {
        "some-model": {
            "backend": "api",
            "cutoff_date": "2023-10-01",
            "cutoff_source": "https://example.com/model-card",
            # num_ctx missing
            "timeout": 30,
            "temperature": 0,
            "seed": 42,
            "structured_output_mode": "JSON",
        }
    }
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(yaml.dump({"models": bad_entry}))
    scores_dir = tmp_path / "scores"
    _make_score_file(scores_dir, {**_PASSING_SCORE, "model_id": "some-model"})

    with pytest.raises(ConfigurationError, match="num_ctx"):
        LLMExtractorFactory(
            registry_path=registry_path,
            scores_dir=scores_dir,
            model_id="some-model",
            base_url=None,
            api_key="test-key",
            prompt_version="v1",
            prefilter_version="v1",
        )


def test_digest_mismatch_fails_at_startup(tmp_path):
    registry_path = _make_registry_file(tmp_path, _VALID_LOCAL_ENTRY)
    scores_dir = tmp_path / "scores"
    model_id = "gemma3:27b@sha256:abc123"
    _make_score_file(scores_dir, {**_PASSING_SCORE, "model_id": model_id})

    def bad_model_info_fn(model_tag: str) -> str:
        return "gemma3:27b@sha256:different999"

    with pytest.raises(ConfigurationError, match="sha256"):
        LLMExtractorFactory(
            registry_path=registry_path,
            scores_dir=scores_dir,
            model_id=model_id,
            base_url=None,
            api_key="test-key",
            prompt_version="v1",
            prefilter_version="v1",
            model_info_fn=bad_model_info_fn,
        )


def test_over_context_prompt_fails_loudly_not_truncated(tmp_path):
    tiny_entry = {
        "gpt-4o-mini-2024-07-18": {
            **_VALID_API_ENTRY["gpt-4o-mini-2024-07-18"],
            "num_ctx": 10,  # absurdly small — any real prompt overflows
        }
    }
    factory = _make_factory(tmp_path, registry_entries=tiny_entry)
    extractor = factory.make_extractor(schema_version="1.0", prompt_version="v1")

    doc = _make_raw(content="BCL11A gene target CRISPR trial")

    with pytest.raises(ContextLengthError):
        extractor.extract(doc, prefilter_version="v1", raw_object_key="key/raw.json")


def test_malformed_json_response_is_counted_and_nothing_is_published(tmp_path, mocker):
    from auspex_ingest.normalizer import IdentityNormalizer

    factory = _make_factory(tmp_path)
    extractor = factory.make_extractor(schema_version="1.0", prompt_version="v1")

    mock_client = mocker.MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("JSON decode error")
    extractor._client = mock_client

    mock_archive = mocker.MagicMock()
    mock_archive.put.return_value = ("raw/key.json", True)
    mock_archive.get_canonical_marker.return_value = None
    mock_producer = mocker.MagicMock()

    doc = _make_raw()
    mock_connector = mocker.MagicMock()
    mock_connector.fetch_since.return_value = [doc]
    mock_connector.provides_canonical_id = False

    pipeline = IngestionPipeline(
        connector=mock_connector,
        archive=mock_archive,
        extractor=extractor,
        producer=mock_producer,
        prefilter=Prefilter.from_vocab(set()),
        normalizer=IdentityNormalizer(),
        now=lambda: __import__("datetime").datetime(2024, 1, 1, tzinfo=__import__("datetime").timezone.utc),
    )
    from datetime import UTC, datetime
    result = pipeline.run("biorxiv", datetime(2024, 1, 1, tzinfo=UTC))

    assert result.failed == 1
    mock_producer.publish_signal.assert_not_called()


def test_timeout_is_isolated_to_document_and_batch_continues(tmp_path, mocker):
    from datetime import UTC, datetime

    from auspex_ingest.normalizer import IdentityNormalizer

    factory = _make_factory(tmp_path)
    extractor = factory.make_extractor(schema_version="1.0", prompt_version="v1")

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise TimeoutError("model timed out")
        return mocker.MagicMock(is_signal=False)

    mock_client = mocker.MagicMock()
    mock_client.chat.completions.create.side_effect = side_effect
    extractor._client = mock_client

    mock_archive = mocker.MagicMock()
    mock_archive.put.return_value = ("raw/key.json", True)
    mock_archive.get_canonical_marker.return_value = None
    mock_producer = mocker.MagicMock()

    doc1 = _make_raw()
    doc2 = _make_raw(content="second document text")
    mock_connector = mocker.MagicMock()
    mock_connector.fetch_since.return_value = [doc1, doc2]
    mock_connector.provides_canonical_id = False

    pipeline = IngestionPipeline(
        connector=mock_connector,
        archive=mock_archive,
        extractor=extractor,
        producer=mock_producer,
        prefilter=Prefilter.from_vocab(set()),
        normalizer=IdentityNormalizer(),
        now=lambda: datetime(2024, 1, 1, tzinfo=UTC),
    )
    result = pipeline.run("biorxiv", datetime(2024, 1, 1, tzinfo=UTC))

    assert result.failed == 1
    assert result.not_signal == 1
    assert call_count == 2


def test_model_server_unreachable_documents_stay_archived_and_not_published(tmp_path, mocker):
    from datetime import UTC, datetime

    from auspex_ingest.normalizer import IdentityNormalizer

    factory = _make_factory(tmp_path)
    extractor = factory.make_extractor(schema_version="1.0", prompt_version="v1")

    mock_client = mocker.MagicMock()
    mock_client.chat.completions.create.side_effect = ConnectionRefusedError("server down")
    extractor._client = mock_client

    mock_archive = mocker.MagicMock()
    mock_archive.put.return_value = ("raw/key.json", True)
    mock_archive.get_canonical_marker.return_value = None
    mock_producer = mocker.MagicMock()

    doc1 = _make_raw()
    doc2 = _make_raw(content="second document text")
    mock_connector = mocker.MagicMock()
    mock_connector.fetch_since.return_value = [doc1, doc2]
    mock_connector.provides_canonical_id = False

    pipeline = IngestionPipeline(
        connector=mock_connector,
        archive=mock_archive,
        extractor=extractor,
        producer=mock_producer,
        prefilter=Prefilter.from_vocab(set()),
        normalizer=IdentityNormalizer(),
        now=lambda: datetime(2024, 1, 1, tzinfo=UTC),
    )
    result = pipeline.run("biorxiv", datetime(2024, 1, 1, tzinfo=UTC))

    assert result.failed == 2
    assert mock_archive.put.call_count == 2
    mock_producer.publish_signal.assert_not_called()


def test_extraction_parameters_come_from_registry_not_hardcoded(tmp_path, mocker):
    factory = _make_factory(tmp_path)
    extractor = factory.make_extractor(schema_version="1.0", prompt_version="v1")

    mock_client = mocker.MagicMock()
    mock_client.chat.completions.create.return_value = mocker.MagicMock(is_signal=False)
    extractor._client = mock_client

    doc = _make_raw()
    extractor.extract(doc, prefilter_version="v1", raw_object_key="raw/key.json")

    call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs.kwargs.get("temperature") == 0
    assert call_kwargs.kwargs.get("seed") == 42


def test_startup_refuses_model_without_passing_gate_record(tmp_path):
    registry_path = _make_registry_file(tmp_path, _VALID_API_ENTRY)
    scores_dir = tmp_path / "scores"
    scores_dir.mkdir()
    # no score file written

    with pytest.raises(GateNotPassedError, match="gpt-4o-mini-2024-07-18"):
        LLMExtractorFactory(
            registry_path=registry_path,
            scores_dir=scores_dir,
            model_id="gpt-4o-mini-2024-07-18",
            base_url=None,
            api_key="test-key",
            prompt_version="v1",
            prefilter_version="v1",
        )


def test_llm_is_never_called_live(tmp_path):
    """pytest-socket disables all outbound connections; this test simply imports the factory
    and constructs it — if anything tries to reach the network, the suite fails."""
    factory = _make_factory(tmp_path)
    assert factory is not None


_SERVICE_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = _SERVICE_ROOT.parents[1]


def test_extraction_prompt_directory_holds_only_the_default_prompt():
    from auspex_ingest.extraction_backend import DEFAULT_PROMPT_VERSION

    prompts = sorted(p.stem for p in (_SERVICE_ROOT / "prompts" / "extraction").glob("*.txt"))

    assert prompts == [DEFAULT_PROMPT_VERSION]


def test_env_example_prompt_version_is_the_service_default():
    import re

    from auspex_ingest.extraction_backend import DEFAULT_PROMPT_VERSION

    env_example = (_REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    (configured,) = re.findall(r"^EXTRACTION_PROMPT_VERSION=(\S+)$", env_example, re.MULTILINE)

    assert configured == DEFAULT_PROMPT_VERSION


def test_committed_gate_records_match_the_active_prompt_and_prefilter():
    from auspex_ingest.extraction_backend import DEFAULT_PROMPT_VERSION
    from auspex_ingest.prefilter import PREFILTER_VERSION

    stale = [
        record.name
        for record in (_REPO_ROOT / "config" / "models" / "scores").glob("*.json")
        if (score := json.loads(record.read_text(encoding="utf-8")))["prompt_version"]
        != DEFAULT_PROMPT_VERSION
        or score["prefilter_version"] != PREFILTER_VERSION
    ]

    assert stale == []
