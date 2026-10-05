import re
from abc import ABC, abstractmethod
from typing import Any


class EntityNormalizer(ABC):
    @abstractmethod
    def normalize_gene(self, gene: str) -> str: ...

    @abstractmethod
    def normalize_company(self, company: str) -> str: ...


class IdentityNormalizer(EntityNormalizer):
    def normalize_gene(self, gene: str) -> str:
        return gene

    def normalize_company(self, company: str) -> str:
        return company


def _gene_key(raw: str) -> str:
    return re.sub(r"[-\s]", "", raw).upper()


def _company_key(raw: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", raw.upper())


def load_sec_company_tickers(data: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for entry in data.values():
        title: str = str(entry.get("title") or "")
        ticker: str = str(entry.get("ticker") or "")
        if title and ticker:
            result[_company_key(title)] = ticker
    return result


class HgncEntityNormalizer(EntityNormalizer):
    # In production, load gene_aliases from a bundled HGNC snapshot and
    # company_tickers via load_sec_company_tickers().
    def __init__(
        self,
        *,
        gene_aliases: dict[str, str],
        company_tickers: dict[str, str],
    ) -> None:
        self._gene_aliases = gene_aliases
        self._company_tickers = company_tickers

    @classmethod
    def from_mappings(
        cls,
        gene_aliases: dict[str, str],
        company_tickers: dict[str, str],
    ) -> HgncEntityNormalizer:
        return cls(gene_aliases=gene_aliases, company_tickers=company_tickers)

    def normalize_gene(self, gene: str) -> str:
        key = _gene_key(gene)
        return self._gene_aliases.get(key, key)

    def normalize_company(self, company: str) -> str:
        key = _company_key(company)
        return self._company_tickers.get(key, company)
