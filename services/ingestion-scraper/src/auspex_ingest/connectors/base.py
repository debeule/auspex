from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime

from ..models import RawDocument


class SourceConnector(ABC):
    """One external source. Registered by a `sources.yaml` entry; shared code never branches on
    the source type.

    `provides_canonical_id` declares that every document carries a `canonical_id`; the pipeline
    counts a document that arrives without one as failed.
    """

    provides_canonical_id: bool = False

    @abstractmethod
    def fetch_since(self, cursor: datetime) -> Iterator[RawDocument]:
        """Yield documents newer than the UTC `cursor`, mapped to `RawDocument`.

        Fetch and map only: archiving, extraction and publishing belong to `IngestionPipeline`.
        Connectors keep no cursor state between calls.
        """
