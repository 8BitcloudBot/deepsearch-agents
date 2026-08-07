"""Tutorial runtime implementations.

Produces MockTutorialRuntime (deterministic offline) and
DeepAgentsTutorialRuntime (real agent.astream()) behind the
TutorialRuntime protocol.
"""

import asyncio
from dataclasses import dataclass
from typing import Protocol

from app.api.context import SessionContext, session_context
from app.api.events import InMemoryEventBus
from app.providers.contracts import ProviderBundle
from app.tools.reports import generate_markdown_report, generate_pdf_report

# ---------------------------------------------------------------------------
# Request / Result value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RuntimeRequest:
    query: str
    context: SessionContext


@dataclass(frozen=True)
class RuntimeResult:
    answer: str
    artifacts: tuple[str, ...]


# ---------------------------------------------------------------------------
# Runtime protocol
# ---------------------------------------------------------------------------


class TutorialRuntime(Protocol):
    async def run(self, request: RuntimeRequest) -> RuntimeResult: ...


# ---------------------------------------------------------------------------
# Deterministic mock runtime
# ---------------------------------------------------------------------------


class MockTutorialRuntime:
    """Deterministic offline runtime — no model, no network.

    Event ordering: tool_started → real provider call → tool_completed.
    Agent events carry agent_name. Never emits task lifecycle events.
    """

    def __init__(self, bundle: ProviderBundle, events: InMemoryEventBus):
        self._bundle = bundle
        self._events = events

    async def run(self, request: RuntimeRequest) -> RuntimeResult:
        tid = request.context.thread_id
        ws = request.context.workspace

        with session_context(request.context):
            self._emit_agent(tid, "agent_started", "mock-research-agent")

            # 1. Web search
            self._emit_tool(tid, "tool_started", "internet_search")
            search_result = await asyncio.to_thread(
                self._bundle.web.search, request.query
            )
            self._emit_tool(tid, "tool_completed", "internet_search")

            # 2. Catalog: list
            self._emit_tool(tid, "tool_started", "list_sql_tables")
            tables = await asyncio.to_thread(self._bundle.catalog.list_tables)
            self._emit_tool(tid, "tool_completed", "list_sql_tables")

            catalog_data: list[str] = []
            for tbl in tables[:3]:
                self._emit_tool(tid, "tool_started", "preview_table")
                preview = await asyncio.to_thread(
                    self._bundle.catalog.preview_table, tbl.name
                )
                self._emit_tool(tid, "tool_completed", "preview_table")
                cols = ", ".join(preview.columns)
                catalog_data.append(
                    f"\n## Table: {tbl.name}\nColumns: {cols}\n"
                    f"Rows: {len(preview.rows)}"
                )

            if tables:
                self._emit_tool(tid, "tool_started", "execute_readonly_query")
                readonly = await asyncio.to_thread(
                    self._bundle.catalog.execute_readonly,
                    f"SELECT * FROM {tables[0].name} LIMIT 5",
                )
                self._emit_tool(tid, "tool_completed", "execute_readonly_query")
                catalog_data.append(f"\nQuery result: {len(readonly.rows)} rows")

            # 3. Knowledge
            self._emit_tool(tid, "tool_started", "list_knowledge_assistants")
            assistants = await asyncio.to_thread(self._bundle.knowledge.list_assistants)
            self._emit_tool(tid, "tool_completed", "list_knowledge_assistants")

            knowledge_answer = ""
            if assistants:
                self._emit_tool(tid, "tool_started", "ask_knowledge_assistant")
                answer = await asyncio.to_thread(
                    self._bundle.knowledge.ask,
                    assistants[0].name,
                    request.query,
                )
                self._emit_tool(tid, "tool_completed", "ask_knowledge_assistant")
                knowledge_answer = answer.answer

            # 4. Optional: read uploaded file
            uploaded_content = ""
            upload_files = list(ws.upload_dir.glob("*"))
            if upload_files:
                self._emit_tool(tid, "tool_started", "read_uploaded_file")
                for fpath in upload_files:
                    # Exception propagates — no swallowing, no fake completed
                    from app.tools.files import read_uploaded_file

                    text = read_uploaded_file(fpath.name)
                    if len(text) > 5000:
                        text = text[:5000] + "\n\n[TRUNCATED]\n"
                    uploaded_content = text
                self._emit_tool(tid, "tool_completed", "read_uploaded_file")

            # 5. Build report content
            report_lines = [
                "# Tutorial Research Report",
                "",
                f"**Query:** {request.query}",
                "",
                "## Provider Modes",
                f"- web_mode: {self._bundle.web_mode}",
                f"- catalog_mode: {self._bundle.catalog_mode}",
                f"- knowledge_mode: {self._bundle.knowledge_mode}",
                "",
                "## Web Search Results",
                f"Found {len(search_result.hits)} hit(s) for query.",
            ]
            for hit in search_result.hits[:3]:
                report_lines.append(f"- [{hit.title}]({hit.url})")
            report_lines.append("")
            report_lines.append("## Catalog Data")
            report_lines.extend(catalog_data)
            if knowledge_answer:
                report_lines.append("")
                report_lines.append("## Knowledge Base")
                report_lines.append(knowledge_answer)
            if uploaded_content:
                report_lines.append("")
                report_lines.append("## Uploaded Source Material")
                report_lines.append(uploaded_content)
            if self._bundle.uses_mock:
                report_lines.insert(
                    2,
                    "> ⚠️ Partially mocked — at least one provider is in mock mode.",
                )
                report_lines.insert(3, "")
            report_text = "\n".join(report_lines)

            # 6. Generate reports
            self._emit_tool(tid, "tool_started", "generate_markdown_report")
            _ = generate_markdown_report(report_text)
            self._emit_tool(tid, "tool_completed", "generate_markdown_report")

            self._emit_tool(tid, "tool_started", "generate_pdf_report")
            _ = generate_pdf_report(report_text)
            self._emit_tool(tid, "tool_completed", "generate_pdf_report")

            self._emit_artifact(tid, "tutorial-report.md", "text/markdown")
            self._emit_artifact(tid, "tutorial-report.pdf", "application/pdf")

            self._emit_agent(tid, "agent_completed", "mock-research-agent")

            return RuntimeResult(
                answer=report_text,
                artifacts=("tutorial-report.md", "tutorial-report.pdf"),
            )

    def _emit_agent(self, tid: str, etype: str, agent_name: str) -> None:
        self._events.emit(tid, etype, agent_name, {"agent_name": agent_name})

    def _emit_tool(self, tid: str, etype: str, tool_name: str) -> None:
        self._events.emit(tid, etype, tool_name, {"tool_name": tool_name})

    def _emit_artifact(self, tid: str, name: str, media_type: str) -> None:
        self._events.emit(
            tid,
            "artifact_created",
            name,
            {"path": name, "name": name, "media_type": media_type},
        )


# ---------------------------------------------------------------------------
# Real DeepAgents runtime (no duplicate tool events from stream)
# ---------------------------------------------------------------------------


class DeepAgentsTutorialRuntime:
    """Real runtime using agent.astream().

    Does NOT duplicate tool events already emitted by LangChain wrappers.
    Only emits agent_started/agent_completed and compensates for missing
    reports. All tool events come from the tool wrappers.
    """

    def __init__(self, graph, bundle: ProviderBundle, events: InMemoryEventBus):
        self._graph = graph
        self._bundle = bundle
        self._events = events

    async def run(self, request: RuntimeRequest) -> RuntimeResult:
        tid = request.context.thread_id

        with session_context(request.context):
            self._events.emit(
                tid,
                "agent_started",
                "tutorial-research-agent",
                {"agent_name": "tutorial-research-agent"},
            )

            input_state = {"messages": [{"role": "user", "content": request.query}]}
            config = {"configurable": {"thread_id": tid}}
            collected_answer: str = ""

            # Track per-call artifact generation (not by file existence)
            artifacts_generated: set[str] = set()

            async for _chunk in self._graph.astream(
                input_state, config, stream_mode="updates"
            ):
                # Tool events are owned by wrappers — do not duplicate.
                # Track agent/subagent signals and collect answer.
                for node_name, update in _chunk.items():
                    if node_name == "__end__":
                        continue
                    if isinstance(update, dict) and "messages" in update:
                        for msg in update["messages"]:
                            # Only the model's own output may become the
                            # answer. Tool/human messages carry raw provider
                            # responses or error reprs and must never be
                            # echoed into reports.
                            if getattr(msg, "type", "") == "ai":
                                content = getattr(msg, "content", "")
                                if isinstance(content, str) and content:
                                    collected_answer += content + "\n"
                            # Detect artifact_created from tool messages
                            if hasattr(msg, "name") and msg.name in (
                                "generate_markdown_report_tool",
                                "generate_pdf_report_tool",
                            ):
                                artifact_name = (
                                    "tutorial-report.md"
                                    if "markdown" in msg.name
                                    else "tutorial-report.pdf"
                                )
                                artifacts_generated.add(artifact_name)

            if not collected_answer.strip():
                collected_answer = "Research completed."

            # Compensate: generate missing reports
            if "tutorial-report.md" not in artifacts_generated:
                report_text = (
                    f"# Tutorial Research Report\n\n"
                    f"**Query:** {request.query}\n\n"
                    f"## Provider Modes\n"
                    f"- web_mode: {self._bundle.web_mode}\n"
                    f"- catalog_mode: {self._bundle.catalog_mode}\n"
                    f"- knowledge_mode: {self._bundle.knowledge_mode}\n\n"
                    f"## Results\n\n{collected_answer}"
                )
                if self._bundle.uses_mock:
                    report_text = "> ⚠️ Partially mocked\n\n" + report_text
                _ = generate_markdown_report(report_text)
                self._events.emit(
                    tid,
                    "artifact_created",
                    "tutorial-report.md",
                    {
                        "path": "tutorial-report.md",
                        "name": "tutorial-report.md",
                        "media_type": "text/markdown",
                    },
                )

            if "tutorial-report.pdf" not in artifacts_generated:
                _ = generate_pdf_report(collected_answer or "Research completed.")
                self._events.emit(
                    tid,
                    "artifact_created",
                    "tutorial-report.pdf",
                    {
                        "path": "tutorial-report.pdf",
                        "name": "tutorial-report.pdf",
                        "media_type": "application/pdf",
                    },
                )

            self._events.emit(
                tid,
                "agent_completed",
                "tutorial-research-agent",
                {"agent_name": "tutorial-research-agent"},
            )

            return RuntimeResult(
                answer=collected_answer.strip(),
                artifacts=("tutorial-report.md", "tutorial-report.pdf"),
            )
