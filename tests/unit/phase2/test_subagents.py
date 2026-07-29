"""Tests for subagent builder — exact contract assertions."""

from langchain_core.tools import tool

from app.agent.subagents import build_tutorial_subagents


def _fake_tool(name: str):
    @tool
    async def _fn() -> str:
        """Fake tool."""
        return name

    _fn.name = name
    return _fn


TOOLS = [  # noqa: F811
    _fake_tool("internet_search"),
    _fake_tool("list_sql_tables"),
    _fake_tool("describe_table"),
    _fake_tool("preview_table"),
    _fake_tool("execute_readonly_query"),
    _fake_tool("list_knowledge_assistants"),
    _fake_tool("ask_knowledge_assistant"),
]


def test_builds_three_subagents():
    subs = build_tutorial_subagents(
        web_tools=[TOOLS[0]],
        catalog_tools=TOOLS[1:5],
        knowledge_tools=TOOLS[5:7],
    )
    assert len(subs) == 3


def test_exact_ordered_names():
    subs = build_tutorial_subagents([], [], [])
    names = [s["name"] for s in subs]
    assert names == ["web-research", "structured-data", "knowledge-base"]


def test_web_research_description_and_prompt():
    subs = build_tutorial_subagents(
        web_tools=[TOOLS[0]],
        catalog_tools=TOOLS[1:5],
        knowledge_tools=TOOLS[5:7],
    )
    wr = subs[0]
    assert "web" in wr["description"].lower()
    assert "internet_search" in wr["system_prompt"]


def test_structured_data_description_and_prompt():
    subs = build_tutorial_subagents(
        web_tools=[TOOLS[0]],
        catalog_tools=TOOLS[1:5],
        knowledge_tools=TOOLS[5:7],
    )
    sd = subs[1]
    assert "structured" in sd["description"].lower()
    assert "execute_readonly_query" in sd["system_prompt"]


def test_knowledge_base_description_and_prompt():
    subs = build_tutorial_subagents(
        web_tools=[TOOLS[0]],
        catalog_tools=TOOLS[1:5],
        knowledge_tools=TOOLS[5:7],
    )
    kb = subs[2]
    assert "knowledge" in kb["description"].lower()
    assert "ask_knowledge_assistant" in kb["system_prompt"]


def test_web_tools_only_in_web_research():
    subs = build_tutorial_subagents(
        web_tools=[TOOLS[0]],
        catalog_tools=TOOLS[1:5],
        knowledge_tools=TOOLS[5:7],
    )
    wr_tool_names = [t.name for t in subs[0]["tools"]]
    assert "internet_search" in wr_tool_names
    assert "execute_readonly_query" not in wr_tool_names
    assert "ask_knowledge_assistant" not in wr_tool_names


def test_catalog_tools_only_in_structured_data():
    subs = build_tutorial_subagents(
        web_tools=[TOOLS[0]],
        catalog_tools=TOOLS[1:5],
        knowledge_tools=TOOLS[5:7],
    )
    sd_tool_names = [t.name for t in subs[1]["tools"]]
    assert len(sd_tool_names) == 4
    for name in [
        "list_sql_tables",
        "describe_table",
        "preview_table",
        "execute_readonly_query",
    ]:
        assert name in sd_tool_names


def test_knowledge_tools_only_in_knowledge_base():
    subs = build_tutorial_subagents(
        web_tools=[TOOLS[0]],
        catalog_tools=TOOLS[1:5],
        knowledge_tools=TOOLS[5:7],
    )
    kb_tool_names = [t.name for t in subs[2]["tools"]]
    assert len(kb_tool_names) == 2
    for name in ["list_knowledge_assistants", "ask_knowledge_assistant"]:
        assert name in kb_tool_names


def test_all_tools_callable_or_base_tool():
    from langchain_core.tools import BaseTool

    subs = build_tutorial_subagents(
        web_tools=[TOOLS[0]],
        catalog_tools=TOOLS[1:5],
        knowledge_tools=TOOLS[5:7],
    )
    for sub in subs:
        for t in sub["tools"]:
            ok = callable(t) or isinstance(t, BaseTool)
            assert ok, f"{sub['name']}.{getattr(t, 'name', t)} not callable/BaseTool"


def test_no_tool_in_multiple_domains():
    subs = build_tutorial_subagents(
        web_tools=[TOOLS[0]],
        catalog_tools=TOOLS[1:5],
        knowledge_tools=TOOLS[5:7],
    )
    all_names = []
    for sub in subs:
        all_names.extend(t.name for t in sub["tools"])
    assert len(all_names) == len(set(all_names)), "Duplicate tool names across domains"
