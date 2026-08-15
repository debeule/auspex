from typing import Any, Optional

from .models import RawDocument, ResearchSignalEvent


class LLMExtractor:
    def __init__(
        self,
        client: Any,
        model: str,
        schema_version: str,
        prompt_version: str,
    ) -> None:
        self._client = client
        self._model = model
        self._schema_version = schema_version
        self._prompt_version = prompt_version

    def extract(
        self, doc: RawDocument, prefilter_version: str, raw_object_key: str
    ) -> Optional[ResearchSignalEvent]:
        raise NotImplementedError("LLMExtractor requires an injected instructor client")
