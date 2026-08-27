"""Lazy Tavily web search adapter."""

from urllib.parse import urlsplit

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

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        search_depth: str = "basic",
        topic: str = "general",
        time_range: str | None = None,
    ) -> SearchResult:
        client = self._get_client()
        delivery_limit = max(0, min(5, max_results))
        candidate_limit = min(10, max(1, delivery_limit * 2))
        try:
            kwargs = {
                "max_results": candidate_limit,
                "include_raw_content": "markdown",
                "search_depth": search_depth,
                "topic": topic,
            }
            if time_range is not None:
                kwargs["time_range"] = time_range
            response = client.search(query, **kwargs)
        except Exception as exc:
            # Never propagate raw SDK text (may carry keys/paths/payloads).
            raise RuntimeError("Tavily search failed") from exc
        results = response.get("results", [])
        candidates = [
            SearchHit(
                title=(r.get("title") or "")[:200],
                url=r.get("url", ""),
                content=(r.get("content") or "")[:8000],
                score=(
                    float(r["score"])
                    if isinstance(r.get("score"), int | float)
                    and not isinstance(r.get("score"), bool)
                    else None
                ),
                published_date=(
                    r.get("published_date")[:64]
                    if isinstance(r.get("published_date"), str)
                    and r.get("published_date").strip()
                    else None
                ),
            )
            for r in results[:candidate_limit]
        ]
        ranked = sorted(
            enumerate(candidates),
            key=lambda item: (
                item[1].score is None,
                -(item[1].score or 0.0),
                item[0],
            ),
        )
        selected: list[tuple[int, SearchHit]] = []
        deferred: list[tuple[int, SearchHit]] = []
        hostname_counts: dict[str, int] = {}
        for item in ranked:
            hostname = (
                urlsplit(item[1].url).hostname or f"invalid-{item[0]}"
            ).casefold()
            if hostname_counts.get(hostname, 0) >= 2:
                deferred.append(item)
                continue
            hostname_counts[hostname] = hostname_counts.get(hostname, 0) + 1
            selected.append(item)
            if len(selected) == delivery_limit:
                break
        if len(selected) < delivery_limit:
            selected.extend(deferred[: delivery_limit - len(selected)])
        return SearchResult(query=query, hits=tuple(hit for _, hit in selected))
