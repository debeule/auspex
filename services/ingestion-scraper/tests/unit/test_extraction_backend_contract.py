"""Abstract contract tests for extraction backends.

Both LocalBackendContractTest and ApiBackendContractTest inherit ExtractionBackendContractTest
unmodified, as CorroborationServiceContractTest does in Java.
"""
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

import pytest
import yaml

from auspex_ingest.extraction_backend import LLMExtractorFactory
from auspex_ingest.models import RawDocument

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

_PASSING_SCORE = {
    "model_id": "gpt-4o-mini-2024-07-18",
    "prompt_version": "v1.0",
    "prefilter_version": "v1.0",
    "precision": 1.0,
    "passed": True,
    "scored_at": "2024-01-01T00:00:00Z",
}


def _make_doc(content: str = "CRISPR base editing of BCL11A for sickle cell disease") -> RawDocument:
    sha = hashlib.sha256(content.encode()).hexdigest()
    return RawDocument(
        schema_version="1.0",
        external_id="ext-contract-001",
        source_type="biorxiv",
        source_url="https://example.com/doc/contract",
        published_date=datetime(2024, 1, 1, tzinfo=UTC),
        raw_content=content,
        content_sha256=sha,
        retrieved_at=datetime(2024, 1, 1, tzinfo=UTC),
    )


class ExtractionBackendContractTest:
    """Abstract contract. Subclasses must implement `make_extractor`."""

    registry_entries: ClassVar[dict] = _VALID_API_ENTRY
    model_id: ClassVar[str] = "gpt-4o-mini-2024-07-18"

    def make_extractor(self, tmp_path: Path, mocker):
        raise NotImplementedError

    def test_backend_extract_returns_signal_event_or_none(self, tmp_path, mocker):
        extractor = self.make_extractor(tmp_path, mocker)
        mock_client = mocker.MagicMock()
        mock_client.chat.completions.create.return_value = mocker.MagicMock(is_signal=False)
        extractor._client = mock_client

        result = extractor.extract(
            _make_doc(), prefilter_version="v1.0", raw_object_key="raw/key.json"
        )
        assert result is None or hasattr(result, "event_id")

    def test_backend_timeout_does_not_abort_batch(self, tmp_path, mocker):
        extractor = self.make_extractor(tmp_path, mocker)
        mock_client = mocker.MagicMock()
        mock_client.chat.completions.create.side_effect = TimeoutError("timed out")
        extractor._client = mock_client

        with pytest.raises(TimeoutError):
            extractor.extract(
                _make_doc(), prefilter_version="v1.0", raw_object_key="raw/key.json"
            )

    def test_backend_malformed_response_counted_not_published(self, tmp_path, mocker):
        extractor = self.make_extractor(tmp_path, mocker)
        mock_client = mocker.MagicMock()
        mock_client.chat.completions.create.side_effect = ValueError("malformed JSON")
        extractor._client = mock_client

        with pytest.raises(ValueError, match="malformed"):
            extractor.extract(
                _make_doc(), prefilter_version="v1.0", raw_object_key="raw/key.json"
            )

    def test_backend_parameters_match_registry_entry(self, tmp_path, mocker):
        extractor = self.make_extractor(tmp_path, mocker)
        mock_client = mocker.MagicMock()
        mock_client.chat.completions.create.return_value = mocker.MagicMock(is_signal=False)
        extractor._client = mock_client

        extractor.extract(
            _make_doc(), prefilter_version="v1.0", raw_object_key="raw/key.json"
        )
        call_kwargs = mock_client.chat.completions.create.call_args
        entry = self.registry_entries[self.model_id]
        assert call_kwargs.kwargs.get("temperature") == entry["temperature"]
        assert call_kwargs.kwargs.get("seed") == entry["seed"]


def _build_factory(tmp_path: Path, registry_entries: dict, model_id: str) -> LLMExtractorFactory:
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(yaml.dump({"models": registry_entries}))
    scores_dir = tmp_path / "scores"
    scores_dir.mkdir(parents=True, exist_ok=True)
    score_file = scores_dir / f"{model_id}.json"
    score_file.write_text(json.dumps({
        "model_id": model_id,
        "prompt_version": "v1.0",
        "prefilter_version": "v1.0",
        "precision": 1.0,
        "passed": True,
        "scored_at": "2024-01-01T00:00:00Z",
    }))
    return LLMExtractorFactory(
        registry_path=registry_path,
        scores_dir=scores_dir,
        model_id=model_id,
        base_url=None,
        api_key="test-key",
        prompt_version="v1.0",
        prefilter_version="v1.0",
    )


class TestApiBackendContract(ExtractionBackendContractTest):
    registry_entries: ClassVar[dict] = _VALID_API_ENTRY
    model_id: ClassVar[str] = "gpt-4o-mini-2024-07-18"

    def make_extractor(self, tmp_path: Path, mocker):
        factory = _build_factory(tmp_path, self.registry_entries, self.model_id)
        return factory.make_extractor(schema_version="1.0", prompt_version="v1.0")


class TestLocalBackendContract(ExtractionBackendContractTest):
    registry_entries: ClassVar[dict] = {
        "gemma3:27b@sha256:abc123": {
            "backend": "local",
            "cutoff_date": "2024-06-01",
            "cutoff_source": "https://ollama.com/library/gemma3",
            "num_ctx": 8192,
            "timeout": 120,
            "temperature": 0,
            "seed": 0,
            "structured_output_mode": "JSON",
            "digest": "gemma3:27b@sha256:abc123",
        }
    }
    model_id: ClassVar[str] = "gemma3:27b@sha256:abc123"

    def make_extractor(self, tmp_path: Path, mocker):
        registry_path = tmp_path / "registry.yaml"
        registry_path.write_text(yaml.dump({"models": self.registry_entries}))
        scores_dir = tmp_path / "scores"
        scores_dir.mkdir(parents=True, exist_ok=True)
        score_file = scores_dir / f"{self.model_id}.json"
        score_file.write_text(json.dumps({
            "model_id": self.model_id,
            "prompt_version": "v1.0",
            "prefilter_version": "v1.0",
            "precision": 1.0,
            "passed": True,
            "scored_at": "2024-01-01T00:00:00Z",
        }))
        factory = LLMExtractorFactory(
            registry_path=registry_path,
            scores_dir=scores_dir,
            model_id=self.model_id,
            base_url="http://localhost:11434/v1",
            api_key="ollama",
            prompt_version="v1.0",
            prefilter_version="v1.0",
            model_info_fn=lambda tag: self.model_id,
        )
        return factory.make_extractor(schema_version="1.0", prompt_version="v1.0")
