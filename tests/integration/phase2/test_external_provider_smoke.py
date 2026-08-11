"""External provider smoke tests (opt-in only)."""

import os

import pytest

pytestmark = pytest.mark.integration

tavily_smoke = pytest.mark.skipif(
    not os.environ.get("PHASE2_TAVILY_SMOKE"),
    reason="PHASE2_TAVILY_SMOKE not set",
)


@tavily_smoke
def test_tavily_search_smoke():
    from app.providers.tavily import TavilyWebProvider

    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        pytest.skip("TAVILY_API_KEY not configured")
    provider = TavilyWebProvider(api_key=key)
    result = provider.search("test query", max_results=2)
    assert len(result.hits) >= 1
    assert result.hits[0].title
