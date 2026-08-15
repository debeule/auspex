from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime

from ..models import RawDocument


class SourceConnector(ABC):
    @abstractmethod
    def fetch_since(self, cursor: datetime) -> Iterator[RawDocument]:
        ...
