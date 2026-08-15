import hashlib
from collections.abc import Iterator
from datetime import datetime, timezone

from ..models import RawDocument
from .base import SourceConnector

_UTC = timezone.utc
_MOCK_CONTENT = [
    ("mock-001", "CRISPR base editing of BCL11A locus for sickle cell disease"),
    ("mock-002", "AAV gene therapy targeting DMD dystrophin mutations in Duchenne patients"),
    ("mock-003", "HBB base editing trial update: Beam Therapeutics BEAM-101 Phase 1 results"),
    ("mock-004", "Lentiviral gene therapy for RAG1 deficiency: Rocket Pharmaceuticals interim data"),
]


class MockConnector(SourceConnector):
    provides_canonical_id = False

    def __init__(self, *, only_first: bool = False) -> None:
        self._only_first = only_first

    def fetch_since(self, cursor: datetime) -> Iterator[RawDocument]:
        entries = _MOCK_CONTENT[:1] if self._only_first else _MOCK_CONTENT
        for ext_id, content in entries:
            sha = hashlib.sha256(content.encode()).hexdigest()
            yield RawDocument(
                schema_version="1.0",
                external_id=ext_id,
                source_type="mock",
                source_url=f"https://mock.example.com/{ext_id}",
                published_date=cursor,
                raw_content=content,
                content_sha256=sha,
                retrieved_at=cursor,
            )
