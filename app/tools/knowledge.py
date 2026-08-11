"""Knowledge base LangChain tools with thread-aware events."""

import asyncio

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.api.events import InMemoryEventBus
from app.knowledge.contracts import KnowledgeRetriever


def _tid(c: RunnableConfig) -> str:
    t = c.get("configurable", {}).get("thread_id")
    if not isinstance(t, str) or not t:
        raise ValueError("RunnableConfig.configurable.thread_id required")
    return t


def create_knowledge_tools(p: KnowledgeRetriever, ev: InMemoryEventBus):
    @tool
    async def search_knowledge(
        query: str, config: RunnableConfig, limit: int = 8
    ) -> str:
        """Retrieve evidence chunks from the configured knowledge index."""
        tid = _tid(config)
        ev.emit(
            tid,
            "tool_started",
            "search_knowledge",
            {"tool_name": "search_knowledge"},
        )
        chunks = await asyncio.to_thread(p.search, query, limit=limit)
        ev.emit(
            tid,
            "tool_completed",
            "search_knowledge",
            {"tool_name": "search_knowledge"},
        )
        if not chunks:
            return "No knowledge evidence found."
        return "\n".join(f"- {chunk.title}: {chunk.content}" for chunk in chunks)

    return [search_knowledge]
