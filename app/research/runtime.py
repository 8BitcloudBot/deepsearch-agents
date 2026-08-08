"""Deterministic offline agent-research runtime.

Reads only the versioned corpus (``data/phase3/sources``) plus the
thread's uploaded files. Never calls a Provider and never touches the
network. Emits Web, Catalog and Knowledge tool events and writes the
shared ``tutorial-report.md``/``tutorial-report.pdf`` artifact names so
the accepted Phase 2 download contract is reused unchanged.

The report is fully deterministic: it carries ``profile:
agent-research``, the corpus ID, the offline source modes and any
uploaded constraint, and contains no secrets, absolute paths or raw
Provider responses. Task lifecycle events remain owned by TaskRegistry.
"""

import re

from app.agent.runtime import RuntimeRequest, RuntimeResult
from app.api.context import session_context
from app.api.events import InMemoryEventBus
from app.research.corpus import load_corpus
from app.tools.reports import generate_markdown_report, generate_pdf_report

TOOL_WEB = "read_web_snapshot"
TOOL_CATALOG = "read_catalog_entry"
TOOL_KNOWLEDGE = "read_knowledge_notes"
TOOL_UPLOAD = "read_uploaded_file"
TOOL_MARKDOWN = "generate_markdown_report"
TOOL_PDF = "generate_pdf_report"

_KIND_LABELS = {
    "web_snapshot": "Web snapshot",
    "catalog": "Catalog",
    "knowledge": "Knowledge",
}
_MAX_UPLOAD_CHARS = 5000

# Untrusted report input (query + uploaded files) only. Curated versioned
# sources are reviewed and keep their content verbatim; no broad security
# framework is introduced.
_REDACTED = "[REDACTED]"
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=_-]+", re.IGNORECASE),
    re.compile(
        r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|password|"
        r"passwd|secret|token)\b\s*[:=]\s*[^\s,;]+"
    ),
)
_ABSOLUTE_PATH_PATTERNS = (
    # Windows drive / UNC, e.g. C:\Users\me\file.txt or \\server\share
    re.compile(r"(?i)(?:[a-z]:\\|\\\\[^\\\s]+)(?:[^\\\s\"']*\\?)*"),
    # POSIX absolute path, e.g. /Users/me/private/file.pem (never a URL)
    re.compile(r"(?<![\w:/])(?:/[\w.~-]+)+"),
)


def _sanitize_untrusted(text: str) -> str:
    """Replace credentials and absolute paths with a stable marker."""
    for pattern in (*_SECRET_PATTERNS, *_ABSOLUTE_PATH_PATTERNS):
        text = pattern.sub(_REDACTED, text)
    return text


class AgentResearchRuntime:
    """Deterministic offline runtime for the ``agent-research`` profile."""

    def __init__(
        self,
        events: InMemoryEventBus,
        manifest_path: str | None = None,
    ):
        self._events = events
        self._manifest_path = manifest_path

    async def run(self, request: RuntimeRequest) -> RuntimeResult:
        tid = request.context.thread_id
        ws = request.context.workspace

        with session_context(request.context):
            corpus = load_corpus(self._manifest_path)
            self._emit_agent(tid, "agent_started", "agent-research-agent")

            by_kind = {source.kind: source for source in corpus.sources}
            report_lines = [
                "# Agent Research Report",
                "",
                "**Profile:** agent-research",
                f"**Corpus ID:** {corpus.corpus_id}",
                f"**Query:** {_sanitize_untrusted(request.query)}",
                "**Execution mode:** offline (deterministic)",
                "",
                "## Source Modes",
            ]
            for kind in ("web_snapshot", "catalog", "knowledge"):
                mode = "offline-versioned" if kind in by_kind else "unavailable"
                report_lines.append(f"- {_KIND_LABELS[kind]}: {mode}")

            # Web, Catalog and Knowledge tool events over the corpus sources
            for kind, tool in (
                ("web_snapshot", TOOL_WEB),
                ("catalog", TOOL_CATALOG),
                ("knowledge", TOOL_KNOWLEDGE),
            ):
                source = by_kind.get(kind)
                if source is None:
                    continue
                self._emit_tool(tid, "tool_started", tool)
                report_lines.append("")
                report_lines.append(f"## {_KIND_LABELS[kind]}: {source.title}")
                report_lines.append(f"- source_id: {source.source_id}")
                report_lines.append(f"- origin: {source.origin}")
                report_lines.append(f"- captured_at: {source.captured_at}")
                report_lines.append("")
                report_lines.append(source.content)
                self._emit_tool(tid, "tool_completed", tool)

            # Uploaded constraints are untrusted source material
            uploaded_content = ""
            for fpath in sorted(ws.upload_dir.glob("*")):
                if not fpath.is_file():
                    continue
                from app.tools.files import read_uploaded_file

                self._emit_tool(tid, "tool_started", TOOL_UPLOAD)
                text = read_uploaded_file(fpath.name)
                # Redact before truncation so a secret straddling the
                # boundary cannot leak its prefix.
                text = _sanitize_untrusted(text)
                if len(text) > _MAX_UPLOAD_CHARS:
                    text = text[:_MAX_UPLOAD_CHARS] + "\n\n[TRUNCATED]\n"
                uploaded_content = text
                self._emit_tool(tid, "tool_completed", TOOL_UPLOAD)
            if uploaded_content:
                report_lines.append("")
                report_lines.append("## Uploaded Constraint")
                report_lines.append(uploaded_content)

            report_text = "\n".join(report_lines) + "\n"

            self._emit_tool(tid, "tool_started", TOOL_MARKDOWN)
            _ = generate_markdown_report(report_text)
            self._emit_tool(tid, "tool_completed", TOOL_MARKDOWN)

            self._emit_tool(tid, "tool_started", TOOL_PDF)
            _ = generate_pdf_report(report_text)
            self._emit_tool(tid, "tool_completed", TOOL_PDF)

            self._emit_artifact(tid, "tutorial-report.md", "text/markdown")
            self._emit_artifact(tid, "tutorial-report.pdf", "application/pdf")

            self._emit_agent(tid, "agent_completed", "agent-research-agent")

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
