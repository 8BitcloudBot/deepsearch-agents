"""Tests for tool event emission with RunnableConfig thread_id."""

import asyncio

import pytest

from app.api.events import InMemoryEventBus
from app.providers.mock import (
    MockCatalogProvider,
    MockKnowledgeProvider,
    MockWebProvider,
)
from app.tools.catalog import create_catalog_tools
from app.tools.knowledge import create_knowledge_tools
from app.tools.web import create_internet_search_tool

ALL_SEVEN = [
    "internet_search",
    "list_sql_tables",
    "describe_table",
    "preview_table",
    "execute_readonly_query",
    "list_knowledge_assistants",
    "ask_knowledge_assistant",
]


async def _collect_events(bus, thread_id):
    events = []
    async with bus.subscribe(thread_id) as sub:
        # Drain all queued events after subscription
        try:
            await asyncio.wait_for(sub.queue.get(), timeout=0.05)
        except TimeoutError:
            pass
        while not sub.queue.empty():
            events.append(sub.queue.get_nowait())
    return events


@pytest.mark.asyncio
async def test_internet_search_emits_paired_events():
    bus = InMemoryEventBus()
    provider = MockWebProvider()
    tool = create_internet_search_tool(provider, bus)

    collected = []
    config = {"configurable": {"thread_id": "thread-42"}}

    async with bus.subscribe("thread-42") as sub:
        result = await tool.ainvoke(
            {"query": "test"}, config=RunnableConfigWrapper(config)
        )
        while not sub.queue.empty():
            collected.append(sub.queue.get_nowait())

    types = [e.type for e in collected]
    assert "tool_started" in types, f"Missing start. got={types}"
    assert "tool_completed" in types, f"Missing complete. got={types}"
    for e in collected:
        assert e.thread_id == "thread-42"


@pytest.mark.asyncio
async def test_all_seven_tools_emit_paired_events():
    bus = InMemoryEventBus()
    web = create_internet_search_tool(MockWebProvider(), bus)
    cat_tools = create_catalog_tools(MockCatalogProvider(), bus)
    k_tools = create_knowledge_tools(MockKnowledgeProvider(), bus)
    all_tools = [web] + cat_tools + k_tools

    config = {"configurable": {"thread_id": "t-main"}}

    async with bus.subscribe("t-main") as sub:
        # Invoke each tool
        for tool in all_tools:
            try:
                if tool.name == "internet_search":
                    await tool.ainvoke({"query": "x"}, config=RunnableConfigWrapper(config))
                elif tool.name == "list_sql_tables":
                    await tool.ainvoke({}, config=RunnableConfigWrapper(config))
                elif tool.name == "describe_table":
                    await tool.ainvoke({"table_name": "drugs"}, config=RunnableConfigWrapper(config))
                elif tool.name == "preview_table":
                    await tool.ainvoke({"table_name": "drugs"}, config=RunnableConfigWrapper(config))
                elif tool.name == "execute_readonly_query":
                    await tool.ainvoke({"query": "SELECT * FROM drugs LIMIT 1"}, config=RunnableConfigWrapper(config))
                elif tool.name == "list_knowledge_assistants":
                    await tool.ainvoke({}, config=RunnableConfigWrapper(config))
                elif tool.name == "ask_knowledge_assistant":
                    await tool.ainvoke(
                        {"assistant_name": "research-assistant", "question": "q"},
                        config=RunnableConfigWrapper(config),
                    )
            except Exception as exc:
                pytest.fail(f"Tool {tool.name} raised: {exc}")

    collected = []
    while not sub.queue.empty():
        collected.append(sub.queue.get_nowait())

    types = [e.type for e in collected]
    assert types.count("tool_started") == 7, f"Expected 7 starts, got {types.count('tool_started')}"
    assert types.count("tool_completed") == 7, f"Expected 7 completes, got {types.count('tool_completed')}"
    for e in collected:
        assert e.thread_id == "t-main"


@pytest.mark.asyncio
async def test_cross_thread_isolation():
    bus = InMemoryEventBus()
    tool = create_internet_search_tool(MockWebProvider(), bus)
    config = {"configurable": {"thread_id": "thread-A"}}

    async with bus.subscribe("thread-A") as sub_a:
        async with bus.subscribe("thread-B") as sub_b:
            await tool.ainvoke({"query": "x"}, config=RunnableConfigWrapper(config))

    events_a = []
    while not sub_a.queue.empty():
        events_a.append(sub_a.queue.get_nowait())

    events_b = []
    while not sub_b.queue.empty():
        events_b.append(sub_b.queue.get_nowait())

    assert len(events_a) >= 2, "Thread-A should receive events"
    assert len(events_b) == 0, "Thread-B should receive nothing"


class RunnableConfigWrapper(dict):
    """Wrapper so LangChain tools accept our config dict."""

    pass
