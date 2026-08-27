"""Provider value objects and protocols used by agent-research adapters."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    content: str
    score: float | None = None
    published_date: str | None = None


@dataclass(frozen=True)
class SearchResult:
    query: str
    hits: tuple[SearchHit, ...]


class WebSearchProvider(Protocol):
    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        search_depth: str = "basic",
        topic: str = "general",
        time_range: str | None = None,
    ) -> SearchResult: ...
