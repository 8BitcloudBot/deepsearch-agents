"""Provider contracts for Phase 2 tutorial."""

from dataclasses import dataclass
from typing import Literal, Protocol


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


@dataclass(frozen=True)
class KnowledgeAssistant:
    name: str
    description: str
    knowledge_bases: tuple[str, ...]


@dataclass(frozen=True)
class KnowledgeAnswer:
    assistant_name: str
    answer: str


class WebSearchProvider(Protocol):
    def search(self, query: str, *, max_results: int = 5) -> SearchResult: ...


class CatalogProvider(Protocol):
    def list_tables(self) -> tuple[TableInfo, ...]: ...

    def describe_table(self, table_name: str) -> QueryResult: ...

    def preview_table(self, table_name: str, *, limit: int = 20) -> QueryResult: ...

    def execute_readonly(self, query: str, *, limit: int = 100) -> QueryResult: ...


class KnowledgeProvider(Protocol):
    def list_assistants(self) -> tuple[KnowledgeAssistant, ...]: ...

    def ask(self, assistant_name: str, question: str) -> KnowledgeAnswer: ...


@dataclass(frozen=True)
class ProviderBundle:
    web: WebSearchProvider
    catalog: CatalogProvider
    knowledge: KnowledgeProvider
    web_mode: Literal["mock", "tavily"]
    catalog_mode: Literal["mock", "mysql"]
    knowledge_mode: Literal["mock", "ragflow"]

    @property
    def uses_mock(self) -> bool:
        return "mock" in (self.web_mode, self.catalog_mode, self.knowledge_mode)
