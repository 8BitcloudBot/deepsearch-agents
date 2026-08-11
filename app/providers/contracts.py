"""Provider contracts for Phase 2 tutorial."""

from dataclasses import dataclass
from typing import Literal, Protocol

from app.knowledge.contracts import KnowledgeRetriever


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    content: str


@dataclass(frozen=True)
class SearchResult:
    query: str
    hits: tuple[SearchHit, ...]


@dataclass(frozen=True)
class TableInfo:
    name: str


@dataclass(frozen=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    truncated: bool


class WebSearchProvider(Protocol):
    def search(self, query: str, *, max_results: int = 5) -> SearchResult: ...


class CatalogProvider(Protocol):
    def list_tables(self) -> tuple[TableInfo, ...]: ...

    def describe_table(self, table_name: str) -> QueryResult: ...

    def preview_table(self, table_name: str, *, limit: int = 20) -> QueryResult: ...

    def execute_readonly(self, query: str, *, limit: int = 100) -> QueryResult: ...


@dataclass(frozen=True)
class ProviderBundle:
    web: WebSearchProvider
    catalog: CatalogProvider
    knowledge: KnowledgeRetriever
    web_mode: Literal["mock", "tavily"]
    catalog_mode: Literal["mock", "mysql"]
    knowledge_mode: Literal["mock", "qdrant-local"]

    @property
    def uses_mock(self) -> bool:
        return "mock" in (self.web_mode, self.catalog_mode, self.knowledge_mode)
