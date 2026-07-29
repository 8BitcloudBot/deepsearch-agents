"""Knowledge base LangChain tools with thread-aware events."""

import asyncio

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.api.events import InMemoryEventBus
from app.providers.contracts import KnowledgeProvider


def _tid(c: RunnableConfig) -> str:
    t = c.get("configurable", {}).get("thread_id")
    if not isinstance(t, str) or not t:
        raise ValueError("RunnableConfig.configurable.thread_id required")
    return t


def create_knowledge_tools(p: KnowledgeProvider, ev: InMemoryEventBus):
    @tool
    async def list_knowledge_assistants(config: RunnableConfig) -> str:
        """List assistants."""
        tid = _tid(config)
        ev.emit(tid, "tool_started", "list", {"tool_name": "list_knowledge_assistants"})
        r = await asyncio.to_thread(p.list_assistants)
        ev.emit(
            tid,
            "tool_completed",
            f"found {len(r)}",
            {"tool_name": "list_knowledge_assistants"},
        )
        return "\n".join(f"- {a.name}: {a.description}" for a in r)

    @tool
    async def ask_knowledge_assistant(an: str, q: str, config: RunnableConfig) -> str:
        """Ask assistant."""
        tid = _tid(config)
        ev.emit(tid, "tool_started", an, {"tool_name": "ask_knowledge_assistant"})
        r = await asyncio.to_thread(p.ask, an, q)
        ev.emit(tid, "tool_completed", "done", {"tool_name": "ask_knowledge_assistant"})
        return f"[{r.assistant_name}] {r.answer}"

    return [list_knowledge_assistants, ask_knowledge_assistant]
