"""Lazy Tavily web search adapter."""

from app.providers.contracts import SearchHit, SearchResult


class TavilyWebProvider:
    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            from tavily import TavilyClient

            self._client = TavilyClient(api_key=self._api_key)
        return self._client

    def search(self, query: str, *, max_results: int = 5) -> SearchResult:
        client = self._get_client()
        response = client.search(
            query, max_results=max_results, include_raw_content=True
        )
        results = response.get("results", [])
        hits = tuple(
            SearchHit(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("raw_content", r.get("content", "")),
            )
            for r in results[:max_results]
        )
        return SearchResult(query=query, hits=hits)
