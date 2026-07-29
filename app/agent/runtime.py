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

    Executes a fixed provider call sequence, reads any uploaded
    Markdown fixture, and generates both report artifacts. Emits
    paired agent/tool and artifact events. Never emits task lifecycle
    or terminal events — those belong to TaskRegistry.
    """

    def __init__(self, bundle: ProviderBundle, events: InMemoryEventBus):
        self._bundle = bundle
        self._events = events

    async def run(self, request: RuntimeRequest) -> RuntimeResult:
        tid = request.context.thread_id
        ws = request.context.workspace

        # Establish session context for tools/reports
        with session_context(request.context):
            # Emit agent started
            self._events.emit(tid, "agent_started", "mock-research-agent", {})

            # 1. Web search
            self._emit_tool_pair(tid, "internet_search", "searching web")
            search_result = await asyncio.to_thread(
                self._bundle.web.search, request.query
            )

            # 2. Catalog: list → preview → read-only query
            self._emit_tool_pair(tid, "list_sql_tables", "listing tables")
            tables = await asyncio.to_thread(self._bundle.catalog.list_tables)

            catalog_data: list[str] = []
            for tbl in tables[:3]:
                self._emit_tool_pair(tid, "preview_table", f"preview {tbl.name}")
                preview = await asyncio.to_thread(
                    self._bundle.catalog.preview_table, tbl.name
                )
                cols = ", ".join(preview.columns)
                catalog_data.append(
                    f"\n## Table: {tbl.name}\nColumns: {cols}\n"
                    f"Rows: {len(preview.rows)}"
                )

            if tables:
                self._emit_tool_pair(tid, "execute_readonly_query", "read-only query")
                readonly = await asyncio.to_thread(
                    self._bundle.catalog.execute_readonly,
                    f"SELECT * FROM {tables[0].name} LIMIT 5",
                )
                catalog_data.append(f"\nQuery result: {len(readonly.rows)} rows")

            # 3. Knowledge: list → ask
            self._emit_tool_pair(tid, "list_knowledge_assistants", "listing assistants")
            assistants = await asyncio.to_thread(self._bundle.knowledge.list_assistants)

            knowledge_answer = ""
            if assistants:
                self._emit_tool_pair(tid, "ask_knowledge_assistant", "asking assistant")
                answer = await asyncio.to_thread(
                    self._bundle.knowledge.ask,
                    assistants[0].name,
                    request.query,
                )
                knowledge_answer = answer.answer

            # 4. Optional: read uploaded file
            uploaded_content = ""
            upload_files = list(ws.upload_dir.glob("*"))
            if upload_files:
                self._emit_tool_pair(tid, "read_uploaded_file", "reading upload")
                for fpath in upload_files:
                    if fpath.suffix.lower() == ".md":
                        try:
                            text = fpath.read_text(encoding="utf-8")
                            if len(text) > 5000:
                                text = text[:5000] + "\n\n[TRUNCATED]\n"
                            uploaded_content = text
                        except Exception:
                            uploaded_content = f"[Could not read {fpath.name}]"

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
            self._emit_tool_pair(tid, "generate_markdown_report", "generating markdown")
            _ = generate_markdown_report(report_text)

            self._emit_tool_pair(tid, "generate_pdf_report", "generating pdf")
            _ = generate_pdf_report(report_text)

            # Emit artifact events
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

            # Emit agent completed
            self._events.emit(
                tid,
                "agent_completed",
                "research complete",
                {},
            )

            return RuntimeResult(
                answer=report_text,
                artifacts=("tutorial-report.md", "tutorial-report.pdf"),
            )

    def _emit_tool_pair(self, tid: str, tool_name: str, message: str) -> None:
        self._events.emit(tid, "tool_started", message, {"tool_name": tool_name})
        self._events.emit(
            tid, "tool_completed", f"done {message}", {"tool_name": tool_name}
        )


# ---------------------------------------------------------------------------
# Real DeepAgents runtime
# ---------------------------------------------------------------------------


class DeepAgentsTutorialRuntime:
    """Real runtime that invokes the compiled agent graph with astream().

    Establishes session_context around the request, invokes
    agent.astream(..., stream_mode="updates"), normalizes agent/
    subagent/tool/result signals into events, writes final reports
    through report tools, and always resets context.

    Errors propagate after context cleanup — TaskRegistry remains
    the sole terminal-event owner.
    """

    def __init__(
        self,
        graph,
        bundle: ProviderBundle,
        events: InMemoryEventBus,
    ):
        self._graph = graph
        self._bundle = bundle
        self._events = events

    async def run(self, request: RuntimeRequest) -> RuntimeResult:
        tid = request.context.thread_id

        with session_context(request.context):
            self._events.emit(tid, "agent_started", "tutorial-research-agent", {})

            input_state = {
                "messages": [
                    {
                        "role": "user",
                        "content": request.query,
                    }
                ]
            }

            config = {"configurable": {"thread_id": tid}}

            collected_answer: str = ""

            async for chunk in self._graph.astream(
                input_state, config, stream_mode="updates"
            ):
                self._normalize_stream_chunk(tid, chunk)
                for _agent_name, update in chunk.items():
                    if isinstance(update, dict) and "messages" in update:
                        for msg in update["messages"]:
                            content = getattr(msg, "content", "")
                            if isinstance(content, str) and content:
                                collected_answer += content + "\n"

            if not collected_answer.strip():
                collected_answer = "Research completed."

            # Generate reports from the collected answer
            report_text = (
                f"# Tutorial Research Report\n\n"
                f"**Query:** {request.query}\n\n"
                f"## Provider Modes\n"
                f"- web_mode: {self._bundle.web_mode}\n"
                f"- catalog_mode: {self._bundle.catalog_mode}\n"
                f"- knowledge_mode: {self._bundle.knowledge_mode}\n\n"
                f"## Results\n\n"
                f"{collected_answer}"
            )

            if self._bundle.uses_mock:
                report_text = (
                    "> ⚠️ Partially mocked — at least one provider"
                    " is in mock mode.\n\n" + report_text
                )

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

            _ = generate_pdf_report(report_text)
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
                "research complete",
                {},
            )

            return RuntimeResult(
                answer=collected_answer.strip(),
                artifacts=("tutorial-report.md", "tutorial-report.pdf"),
            )

    def _normalize_stream_chunk(self, tid: str, chunk: dict) -> None:
        """Normalize langgraph stream chunk into agent/tool events."""
        for node_name, update in chunk.items():
            if node_name == "__end__":
                continue
            if isinstance(update, dict) and "messages" in update:
                messages = update.get("messages", [])
                for msg in messages:
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            tool_name = tc.get("name", "unknown")
                            self._events.emit(
                                tid,
                                "tool_started",
                                tool_name,
                                {"tool_name": tool_name},
                            )
            if node_name == "tools":
                if isinstance(update, dict) and "messages" in update:
                    for msg in update.get("messages", []):
                        if hasattr(msg, "name"):
                            self._events.emit(
                                tid,
                                "tool_completed",
                                msg.name,
                                {"tool_name": msg.name},
                            )
