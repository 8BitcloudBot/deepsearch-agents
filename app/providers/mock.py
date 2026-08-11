"""Deterministic mock adapters for offline testing."""

from app.knowledge.contracts import KnowledgeChunk
from app.providers.contracts import (
    QueryResult,
    SearchHit,
    SearchResult,
    TableInfo,
)

_FIXED_HITS = (
    SearchHit(
        title="DeepAgents Documentation",
        url="https://docs.deepagents.ai/",
        content="DeepAgents is a framework for building agent systems.",
    ),
    SearchHit(
        title="LangGraph Checkpointing",
        url="https://langchain-ai.github.io/langgraph/",
        content="LangGraph supports checkpointing via MemorySaver.",
    ),
)

_FIXED_TABLES = {
    "drugs": QueryResult(
        columns=("id", "name", "category", "price"),
        rows=(
            (1, "Aspirin", "NSAID", 5.99),
            (2, "Ibuprofen", "NSAID", 7.49),
        ),
        truncated=False,
    ),
    "inventory": QueryResult(
        columns=("drug_id", "quantity", "warehouse"),
        rows=((1, 100, "WH-A"), (2, 50, "WH-B")),
        truncated=False,
    ),
    "sales_records": QueryResult(
        columns=("id", "drug_id", "date", "amount"),
        rows=((1, 1, "2026-01-15", 3), (2, 2, "2026-01-16", 2)),
        truncated=False,
    ),
}


class MockWebProvider:
    def search(self, query: str, *, max_results: int = 5) -> SearchResult:
        return SearchResult(query=query, hits=tuple(_FIXED_HITS[:max_results]))


class MockCatalogProvider:
    def list_tables(self) -> tuple[TableInfo, ...]:
        return tuple(TableInfo(name=n) for n in sorted(_FIXED_TABLES))

    def describe_table(self, table_name: str) -> QueryResult:
        if table_name not in _FIXED_TABLES:
            raise ValueError(f"Unknown table: {table_name!r}")
        return _FIXED_TABLES[table_name]

    def preview_table(self, table_name: str, *, limit: int = 20) -> QueryResult:
        result = self.describe_table(table_name)
        return QueryResult(
            columns=result.columns,
            rows=result.rows[:limit],
            truncated=len(result.rows) > limit,
        )

    def execute_readonly(self, query: str, *, limit: int = 100) -> QueryResult:
        # Simplistic: parse table name from query
        for tname in _FIXED_TABLES:
            if tname in query.lower():
                return QueryResult(
                    columns=_FIXED_TABLES[tname].columns,
                    rows=_FIXED_TABLES[tname].rows[:limit],
                    truncated=len(_FIXED_TABLES[tname].rows) > limit,
                )
        raise ValueError(f"No mock table matched query: {query!r}")


class MockKnowledgeRetriever:
    """Deterministic offline retriever returning evidence chunks only."""

    _chunks = (
        KnowledgeChunk(
            collection_id="tutorial-knowledge",
            document_id="tutorial-research-notes",
            chunk_id="chunk-0001",
            title="Tutorial research notes",
            content="Research indicates relevant findings for the requested topic.",
            score=1.0,
            version="1.0.0",
        ),
    )

    def search(
        self, query: str, *, collection_id=None, limit=8, document_version=None
    ) -> tuple[KnowledgeChunk, ...]:
        del query
        chunks = self._chunks
        if collection_id is not None:
            chunks = tuple(
                chunk for chunk in chunks if chunk.collection_id == collection_id
            )
        if document_version is not None:
            chunks = tuple(
                chunk for chunk in chunks if chunk.version == document_version
            )
        return chunks[:limit]
