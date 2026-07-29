"""Tutorial agent factory — pure assembly of the DeepAgents graph.

Accepts model, ProviderBundle, InMemoryEventBus, workspace_factory,
and returns a compiled agent graph.
"""

from collections.abc import Callable
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from app.agent.prompts import MAIN_PROMPT
from app.agent.subagents import build_tutorial_subagents
from app.api.events import InMemoryEventBus
from app.providers.contracts import ProviderBundle
from app.tools.catalog import create_catalog_tools
from app.tools.knowledge import create_knowledge_tools
from app.tools.web import create_internet_search_tool


def create_tutorial_agent(
    model: Any,
    bundle: ProviderBundle,
    events: InMemoryEventBus,
    workspace_factory: Callable[[str], Any] | None = None,
):
    """Assemble the tutorial-research-agent DeepAgents graph.

    workspace_factory is reserved for per-thread workspace assembly.
    """
    from deepagents import create_deep_agent

    # Domain tools → each goes exclusively to its subagent
    web_tools = [create_internet_search_tool(bundle.web, events)]
    catalog_tools = create_catalog_tools(bundle.catalog, events)
    knowledge_tools = create_knowledge_tools(bundle.knowledge, events)

    subagents = build_tutorial_subagents(web_tools, catalog_tools, knowledge_tools)

    # Main-level tools: file reader + report generators
    main_tools = _create_main_tools(events)

    return create_deep_agent(
        model=model,
        tools=main_tools,
        system_prompt=MAIN_PROMPT,
        subagents=subagents,
        checkpointer=InMemorySaver(),
        name="tutorial-research-agent",
    )


# ---------------------------------------------------------------------------
# Main-level tool builders
# ---------------------------------------------------------------------------


def _create_main_tools(events: InMemoryEventBus):
    return [
        _build_read_uploaded_file_tool(events),
        _build_generate_markdown_tool(events),
        _build_generate_pdf_tool(events),
    ]


def _build_read_uploaded_file_tool(events: InMemoryEventBus):
    import asyncio

    from langchain_core.runnables import RunnableConfig
    from langchain_core.tools import tool

    from app.tools.files import read_uploaded_file

    @tool("read_uploaded_file")
    async def _read_uploaded_file_impl(filename: str, config: RunnableConfig) -> str:
        """Read an uploaded file from the session workspace.

        Args:
            filename: Name of the uploaded file to read.
        """
        tid = _thread_id(config)
        events.emit(
            tid,
            "tool_started",
            f"reading {filename}",
            {"tool_name": "read_uploaded_file"},
        )
        try:
            content = await asyncio.to_thread(read_uploaded_file, filename)
            events.emit(
                tid,
                "tool_completed",
                f"read {filename}",
                {"tool_name": "read_uploaded_file"},
            )
            return content
        except Exception:
            events.emit(
                tid,
                "tool_completed",
                f"failed {filename}",
                {"tool_name": "read_uploaded_file"},
            )
            raise

    return _read_uploaded_file_impl


def _build_generate_markdown_tool(events: InMemoryEventBus):
    from langchain_core.runnables import RunnableConfig
    from langchain_core.tools import tool

    from app.tools.reports import generate_markdown_report

    @tool
    async def generate_markdown_report_tool(
        content: str, config: RunnableConfig
    ) -> str:
        """Generate a Markdown report from the given content."""
        tid = _thread_id(config)
        events.emit(
            tid,
            "tool_started",
            "generating markdown report",
            {"tool_name": "generate_markdown_report"},
        )
        _ = generate_markdown_report(content)
        events.emit(
            tid,
            "artifact_created",
            "tutorial-report.md",
            {
                "tool_name": "generate_markdown_report",
                "path": "tutorial-report.md",
                "name": "tutorial-report.md",
                "media_type": "text/markdown",
            },
        )
        events.emit(
            tid,
            "tool_completed",
            "markdown report created",
            {"tool_name": "generate_markdown_report"},
        )
        return f"Report written to tutorial-report.md\n\n{content}"

    return generate_markdown_report_tool


def _build_generate_pdf_tool(events: InMemoryEventBus):
    from langchain_core.runnables import RunnableConfig
    from langchain_core.tools import tool

    from app.tools.reports import generate_pdf_report

    @tool
    async def generate_pdf_report_tool(content: str, config: RunnableConfig) -> str:
        """Generate a PDF report from the given Markdown content.

        Args:
            content: The report content in Markdown format.
        """
        tid = _thread_id(config)
        events.emit(
            tid,
            "tool_started",
            "generating pdf report",
            {"tool_name": "generate_pdf_report"},
        )
        _ = generate_pdf_report(content)
        events.emit(
            tid,
            "artifact_created",
            "tutorial-report.pdf",
            {
                "tool_name": "generate_pdf_report",
                "path": "tutorial-report.pdf",
                "name": "tutorial-report.pdf",
                "media_type": "application/pdf",
            },
        )
        events.emit(
            tid,
            "tool_completed",
            "pdf report created",
            {"tool_name": "generate_pdf_report"},
        )
        return "PDF report generated successfully."

    return generate_pdf_report_tool


def _thread_id(config) -> str:
    t = config.get("configurable", {}).get("thread_id")
    if not isinstance(t, str) or not t:
        raise ValueError("RunnableConfig.configurable.thread_id required")
    return t
