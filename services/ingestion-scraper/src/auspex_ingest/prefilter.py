from .models import RawDocument


class Prefilter:
    def __init__(self, vocab: frozenset[str], version: str = "v1") -> None:
        self._vocab = frozenset(t.lower() for t in vocab)
        self.version = version

    @classmethod
    def from_vocab(
        cls, vocab: set[str] | frozenset[str], version: str = "v1"
    ) -> Prefilter:
        return cls(frozenset(vocab), version)

    def passes(self, doc: RawDocument) -> bool:
        if not self._vocab:
            return True
        text = doc.raw_content.lower()
        return any(term in text for term in self._vocab)
