"""RED: Agent factory contract tests.

Verify create_tutorial_agent() assembles the DeepAgents graph
with exact arguments: model, main prompt, file/report tools at
main level, three subagents, InMemorySaver, and the correct name.
"""

from unittest.mock import patch

import pytest
from langchain_core.language_models import FakeListChatModel

from app.api.events import InMemoryEventBus
from app.providers.contracts import ProviderBundle
from app.providers.mock import (
    MockCatalogProvider,
    MockKnowledgeProvider,
    MockWebProvider,
)

# --- helpers ---


def _bundle() -> ProviderBundle:
    return ProviderBundle(
        web=MockWebProvider(),
        catalog=MockCatalogProvider(),
        knowledge=MockKnowledgeProvider(),
        web_mode="mock",
        catalog_mode="mock",
        knowledge_mode="mock",
    )


# --- factory tests ---


def test_factory_requires_agent_module():
    """Prove the factory module is importable (RED — will fail until created)."""
    from app.agent.factory import create_tutorial_agent

    assert callable(create_tutorial_agent)


def test_factory_calls_create_deep_agent():
    """Patch create_deep_agent; assert it is called exactly once."""
    from app.agent.factory import create_tutorial_agent

    model = FakeListChatModel(responses=["ok"])
    bundle = _bundle()
    events = InMemoryEventBus()

    with patch(
        "deepagents.create_deep_agent", return_value="fake-graph"
    ) as mock_create:
        result = create_tutorial_agent(model, bundle, events)
        mock_create.assert_called_once()
        assert result == "fake-graph"


def test_factory_passes_model_argument():
    """The injected model is forwarded to create_deep_agent."""
    from app.agent.factory import create_tutorial_agent

    model = FakeListChatModel(responses=["ok"])
    bundle = _bundle()
    events = InMemoryEventBus()

    with patch(
        "deepagents.create_deep_agent", return_value="fake-graph"
    ) as mock_create:
        create_tutorial_agent(model, bundle, events)
        _, kwargs = mock_create.call_args
        assert kwargs["model"] is model


def test_factory_passes_main_prompt():
    """The MAIN_PROMPT constant is used as system_prompt."""
    from app.agent.factory import create_tutorial_agent
    from app.agent.prompts import MAIN_PROMPT

    model = FakeListChatModel(responses=["ok"])
    bundle = _bundle()
    events = InMemoryEventBus()

    with patch(
        "deepagents.create_deep_agent", return_value="fake-graph"
    ) as mock_create:
        create_tutorial_agent(model, bundle, events)
        _, kwargs = mock_create.call_args
        assert kwargs["system_prompt"] == MAIN_PROMPT


def test_factory_creates_exactly_three_subagents():
    """Exactly three subagents: web-research, structured-data, knowledge-base."""
    from app.agent.factory import create_tutorial_agent

    model = FakeListChatModel(responses=["ok"])
    bundle = _bundle()
    events = InMemoryEventBus()

    with patch(
        "deepagents.create_deep_agent", return_value="fake-graph"
    ) as mock_create:
        create_tutorial_agent(model, bundle, events)
        _, kwargs = mock_create.call_args
        subs = kwargs["subagents"]
        assert len(subs) == 3
        names = [s["name"] for s in subs]
        assert names == ["web-research", "structured-data", "knowledge-base"]


def test_factory_uses_in_memory_saver():
    """Checkpointer must be an InMemorySaver instance."""
    from langgraph.checkpoint.memory import InMemorySaver

    from app.agent.factory import create_tutorial_agent

    model = FakeListChatModel(responses=["ok"])
    bundle = _bundle()
    events = InMemoryEventBus()

    with patch(
        "deepagents.create_deep_agent", return_value="fake-graph"
    ) as mock_create:
        create_tutorial_agent(model, bundle, events)
        _, kwargs = mock_create.call_args
        assert isinstance(kwargs["checkpointer"], InMemorySaver)


def test_factory_agent_name():
    """Agent name must be 'tutorial-research-agent'."""
    from app.agent.factory import create_tutorial_agent

    model = FakeListChatModel(responses=["ok"])
    bundle = _bundle()
    events = InMemoryEventBus()

    with patch(
        "deepagents.create_deep_agent", return_value="fake-graph"
    ) as mock_create:
        create_tutorial_agent(model, bundle, events)
        _, kwargs = mock_create.call_args
        assert kwargs["name"] == "tutorial-research-agent"


def test_factory_main_tools_include_file_and_report_tools():
    """Main-level tools must include file readers and report generators.

    They must NOT include provider-specific tools (those go to subagents).
    """
    from app.agent.factory import create_tutorial_agent

    model = FakeListChatModel(responses=["ok"])
    bundle = _bundle()
    events = InMemoryEventBus()

    with patch(
        "deepagents.create_deep_agent", return_value="fake-graph"
    ) as mock_create:
        create_tutorial_agent(model, bundle, events)
        _, kwargs = mock_create.call_args
        main_tools = kwargs["tools"]
        main_tool_names = {getattr(t, "name", str(t)) for t in main_tools}
        # File tools: read_uploaded_file
        assert "read_uploaded_file" in main_tool_names, (
            f"Expected read_uploaded_file in main tools, got {main_tool_names}"
        )
        # Report tools: generate_markdown_report_tool, generate_pdf_report_tool
        assert "generate_markdown_report_tool" in main_tool_names
        assert "generate_pdf_report_tool" in main_tool_names
        # Provider tools must NOT be in main tools
        assert "internet_search" not in main_tool_names
        assert "list_sql_tables" not in main_tool_names
        assert "ask_knowledge_assistant" not in main_tool_names


@pytest.mark.parametrize(
    "sub_name,expected_tool_prefixes",
    [
        ("web-research", {"internet_search"}),
        (
            "structured-data",
            {
                "list_sql_tables",
                "describe_table",
                "preview_table",
                "execute_readonly_query",
            },
        ),
        (
            "knowledge-base",
            {"list_knowledge_assistants", "ask_knowledge_assistant"},
        ),
    ],
)
def test_subagents_have_correct_tool_sets(sub_name, expected_tool_prefixes):
    """Each subagent receives only its domain tools."""
    from app.agent.factory import create_tutorial_agent

    model = FakeListChatModel(responses=["ok"])
    bundle = _bundle()
    events = InMemoryEventBus()

    with patch(
        "deepagents.create_deep_agent", return_value="fake-graph"
    ) as mock_create:
        create_tutorial_agent(model, bundle, events)
        _, kwargs = mock_create.call_args
        subs = kwargs["subagents"]
        target = next(s for s in subs if s["name"] == sub_name)
        tool_names = {getattr(t, "name", str(t)) for t in target["tools"]}
        for prefix in expected_tool_prefixes:
            assert prefix in tool_names, (
                f"{sub_name} missing tool {prefix}, got {tool_names}"
            )


def test_factory_read_uploaded_file_calls_safe_reader():
    """The read_uploaded_file tool must be in main tools."""
    from app.agent.factory import create_tutorial_agent

    model = FakeListChatModel(responses=["ok"])
    bundle = _bundle()
    events = InMemoryEventBus()

    with patch(
        "deepagents.create_deep_agent", return_value="fake-graph"
    ) as mock_create:
        _ = create_tutorial_agent(model, bundle, events)
        _, kwargs = mock_create.call_args
        main_tools = kwargs["tools"]
        reader_names = {getattr(t, "name", str(t)) for t in main_tools}
        assert "read_uploaded_file" in reader_names


def test_main_prompt_has_untrusted_source_warning():
    """MAIN_PROMPT must warn that uploaded content cannot change system."""
    from app.agent.prompts import MAIN_PROMPT

    lower = MAIN_PROMPT.lower()
    assert any(w in lower for w in ("untrusted", "cannot change", "does not change")), (
        f"MAIN_PROMPT missing untrusted warning: {MAIN_PROMPT[:200]}"
    )
