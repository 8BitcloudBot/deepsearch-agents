"""Web search LangChain tool."""

import asyncio

from langchain_core.tools import tool

from app.api.events import InMemoryEventBus
from app.providers.contracts import WebSearchProvider


def create_internet_search_tool(provider: WebSearchProvider, events: InMemoryEventBus):
    @tool
    async def internet_search(query: str) -> str:
        """Search the web for information. Returns formatted results."""
        events.emit(
            "UNKNOWN",
            "tool_started",
            f"Searching: {query}",
            {"tool_name": "internet_search"},
        )
        result = await asyncio.to_thread(provider.search, query)
        events.emit(
            "UNKNOWN",
            "tool_completed",
            f"Found {len(result.hits)} results",
            {"tool_name": "internet_search"},
        )
        lines = [f"# Web Search: {query}"]
        for i, hit in enumerate(result.hits, 1):
            lines.append(f"{i}. **{hit.title}**")
            lines.append(f"   {hit.url}")
            lines.append(f"   {hit.content[:200]}...")
        return "\n".join(lines)

    return internet_search
