"""Web search LangChain tool with thread-aware events."""

import asyncio

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.api.events import InMemoryEventBus
from app.providers.contracts import WebSearchProvider


def _tid(c: RunnableConfig) -> str:
    t = c.get("configurable", {}).get("thread_id")
    if not isinstance(t, str) or not t:
        raise ValueError("RunnableConfig.configurable.thread_id required")
    return t


def create_internet_search_tool(p: WebSearchProvider, ev: InMemoryEventBus):
    @tool
    async def internet_search(query: str, config: RunnableConfig) -> str:
        """Search the web."""
        tid = _tid(config)
        ev.emit(tid, "tool_started", "search", {"tool_name": "internet_search"})
        r = await asyncio.to_thread(p.search, query)
        ev.emit(
            tid,
            "tool_completed",
            f"found {len(r.hits)}",
            {"tool_name": "internet_search"},
        )
        lines = [f"# Web Search: {query}"]
        for i, h in enumerate(r.hits, 1):
            lines.append(f"{i}. **{h.title}**\n   {h.url}")
        return "\n".join(lines)

    return internet_search
