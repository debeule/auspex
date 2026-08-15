from abc import ABC, abstractmethod


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
