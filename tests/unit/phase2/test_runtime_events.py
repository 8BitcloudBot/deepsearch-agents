"""RED: Mock runtime event contract.

MockTutorialRuntime must:
- Call all three providers from the injected bundle.
- Consume an optional uploaded Markdown fixture.
- Create both artifacts (tutorial-report.md, tutorial-report.pdf).
- Emit paired agent/tool and artifact events.
- NEVER emit task lifecycle or terminal events.
"""

from pathlib import Path

import pytest

from app.agent.runtime import MockTutorialRuntime, RuntimeRequest, RuntimeResult
from app.api.context import SessionContext
from app.api.events import InMemoryEventBus
from app.providers.contracts import (
    KnowledgeAnswer,
    KnowledgeAssistant,
    ProviderBundle,
    TableInfo,
)
from app.providers.mock import (
    MockCatalogProvider,
    MockKnowledgeProvider,
    MockWebProvider,
)
from app.tools.files import SessionWorkspace

THREAD_ID = "00000000-0000-4000-8000-000000000001"


def _bundle() -> ProviderBundle:
    return ProviderBundle(
        web=MockWebProvider(),
        catalog=MockCatalogProvider(),
        knowledge=MockKnowledgeProvider(),
        web_mode="mock",
        catalog_mode="mock",
        knowledge_mode="mock",
    )


@pytest.fixture
def workspace(tmp_path: Path) -> SessionWorkspace:
    base_upload = tmp_path / "updated"
    base_output = tmp_path / "output"
    return SessionWorkspace.for_thread(
        thread_id=THREAD_ID,
        base_upload=str(base_upload),
        base_output=str(base_output),
    )


@pytest.fixture
def events():
    return InMemoryEventBus()


@pytest.fixture
def runtime(bundle: ProviderBundle, events: InMemoryEventBus):
    """Construct a MockTutorialRuntime (RED — fails until implemented)."""
    from app.agent.runtime import MockTutorialRuntime

    return MockTutorialRuntime(bundle, events)


@pytest.fixture
def bundle():
    return _bundle()


@pytest.fixture
def context(workspace):
    return SessionContext(thread_id=THREAD_ID, workspace=workspace)


# --- Runtime protocol shape ---


def test_runtime_request_is_frozen_dataclass():
    """RuntimeRequest is a frozen dataclass with query and context fields."""
    ws = SessionWorkspace.for_thread(
        thread_id=THREAD_ID,
        base_upload="/tmp/up",
        base_output="/tmp/out",
    )
    ctx = SessionContext(thread_id=THREAD_ID, workspace=ws)
    req = RuntimeRequest(query="test query", context=ctx)
    assert req.query == "test query"
    assert req.context is ctx
    # Frozen check
    with pytest.raises(Exception):
        req.query = "changed"  # type: ignore[misc]


def test_runtime_result_is_frozen_dataclass():
    """RuntimeResult is a frozen dataclass with answer and artifacts."""
    result = RuntimeResult(answer="answer text", artifacts=("a.md", "b.pdf"))
    assert result.answer == "answer text"
    assert result.artifacts == ("a.md", "b.pdf")
    with pytest.raises(Exception):
        result.answer = "changed"  # type: ignore[misc]


# --- Mock runtime event contract ---


@pytest.mark.asyncio
async def test_mock_runtime_completes_full_tutorial_flow(
    runtime, workspace, context, events
):
    """End-to-end mock flow: run, subscribe, collect events, verify artifacts."""
    async with events.subscribe(THREAD_ID) as subscription:
        result = await runtime.run(RuntimeRequest("compare sources", context))
        # Drain all events from queue
        emitted = []
        while not subscription.queue.empty():
            emitted.append(subscription.queue.get_nowait())

    assert isinstance(result, RuntimeResult)
    assert result.artifacts == ("tutorial-report.md", "tutorial-report.pdf")

    event_types = [event.type for event in emitted]
    assert "artifact_created" in event_types, (
        f"Expected artifact_created in {event_types}"
    )
    assert not {
        "task_started",
        "task_completed",
        "task_cancelled",
        "task_failed",
    } & set(event_types), f"Task lifecycle events leaked into runtime: {event_types}"


@pytest.mark.asyncio
async def test_mock_runtime_emits_paired_agent_events(
    runtime, workspace, context, events
):
    """agent_started and agent_completed must both appear."""
    async with events.subscribe(THREAD_ID) as subscription:
        await runtime.run(RuntimeRequest("test", context))
        emitted = []
        while not subscription.queue.empty():
            emitted.append(subscription.queue.get_nowait())

    types = [e.type for e in emitted]
    assert "agent_started" in types, f"Missing agent_started in {types}"
    assert "agent_completed" in types, f"Missing agent_completed in {types}"


@pytest.mark.asyncio
async def test_mock_runtime_emits_paired_tool_events(
    runtime, workspace, context, events
):
    """tool_started and tool_completed must both appear (at least one pair)."""
    async with events.subscribe(THREAD_ID) as subscription:
        await runtime.run(RuntimeRequest("test", context))
        emitted = []
        while not subscription.queue.empty():
            emitted.append(subscription.queue.get_nowait())

    types = [e.type for e in emitted]
    assert "tool_started" in types, f"Missing tool_started in {types}"
    assert "tool_completed" in types, f"Missing tool_completed in {types}"


@pytest.mark.asyncio
async def test_mock_runtime_emits_artifact_events(runtime, workspace, context, events):
    """At least two artifact_created events (one per report)."""
    async with events.subscribe(THREAD_ID) as subscription:
        await runtime.run(RuntimeRequest("test", context))
        emitted = []
        while not subscription.queue.empty():
            emitted.append(subscription.queue.get_nowait())

    artifacts = [e for e in emitted if e.type == "artifact_created"]
    # One for Markdown, one for PDF
    assert len(artifacts) >= 2, f"Expected >=2 artifact_created, got {len(artifacts)}"


@pytest.mark.asyncio
async def test_mock_runtime_never_emits_task_events(
    runtime, workspace, context, events
):
    """Runtime must not emit task lifecycle or terminal events."""
    async with events.subscribe(THREAD_ID) as subscription:
        await runtime.run(RuntimeRequest("test", context))
        emitted = []
        while not subscription.queue.empty():
            emitted.append(subscription.queue.get_nowait())

    forbidden = {"task_started", "task_completed", "task_cancelled", "task_failed"}
    actual_forbidden = [e for e in emitted if e.type in forbidden]
    assert not actual_forbidden, (
        "Runtime emitted task events: "
        f"{[(e.type, e.message) for e in actual_forbidden]}"
    )


@pytest.mark.asyncio
async def test_mock_runtime_creates_report_files(runtime, workspace, context, events):
    """Both tutorial-report.md and tutorial-report.pdf exist on disk after run."""
    async with events.subscribe(THREAD_ID) as _subscription:
        await runtime.run(RuntimeRequest("test", context))

    md_path = workspace.resolve_output("tutorial-report.md")
    pdf_path = workspace.resolve_output("tutorial-report.pdf")
    assert md_path.exists(), f"Missing {md_path}"
    assert pdf_path.exists(), f"Missing {pdf_path}"


@pytest.mark.asyncio
async def test_mock_runtime_report_contains_provider_modes(
    runtime, workspace, context, events
):
    """The generated report must include the provider mode fields."""
    async with events.subscribe(THREAD_ID) as _subscription:
        await runtime.run(RuntimeRequest("test", context))

    md_path = workspace.resolve_output("tutorial-report.md")
    content = md_path.read_text()
    assert "mock" in content.lower(), "Report should mention mock mode"
    assert "web_mode" in content or "web" in content.lower()


@pytest.mark.asyncio
async def test_mock_runtime_consumes_uploaded_fixture(tmp_path, events, bundle):
    """When an uploaded .md fixture exists, the runtime reads and includes it."""
    from app.agent.runtime import MockTutorialRuntime

    thread_id = "00000000-0000-4000-8000-000000000002"
    base_upload = tmp_path / "updated"
    base_output = tmp_path / "output"
    ws = SessionWorkspace.for_thread(
        thread_id=thread_id,
        base_upload=str(base_upload),
        base_output=str(base_output),
    )
    # Create an uploaded fixture
    fixture_md = ws.resolve_upload("constraints.md")
    fixture_md.write_text("# Constraint: keep it short")

    ctx = SessionContext(thread_id=thread_id, workspace=ws)
    rt = MockTutorialRuntime(bundle, events)

    async with events.subscribe(thread_id) as _sub:
        result = await rt.run(RuntimeRequest("compare sources", ctx))

    assert "tutorial-report.md" in result.artifacts
    report = ws.resolve_output("tutorial-report.md")
    content = report.read_text()
    assert "Constraint" in content or "constraint" in content.lower(), (
        f"Report should reference uploaded fixture, got: {content[:200]}"
    )


@pytest.mark.asyncio
async def test_mock_runtime_uses_all_three_providers(
    runtime, workspace, context, events
):
    """Mock runtime must call web, catalog, and knowledge providers."""
    async with events.subscribe(THREAD_ID) as subscription:
        await runtime.run(RuntimeRequest("test", context))
        emitted = []
        while not subscription.queue.empty():
            emitted.append(subscription.queue.get_nowait())

    tool_names = {e.data.get("tool_name") for e in emitted if "tool_name" in e.data}
    # Each domain should have at least one tool call
    web_tools = {"internet_search"}
    catalog_tools = {
        "list_sql_tables",
        "describe_table",
        "preview_table",
        "execute_readonly_query",
    }
    knowledge_tools = {"list_knowledge_assistants", "ask_knowledge_assistant"}

    assert tool_names & web_tools, f"No web tool calls in {tool_names}"
    assert tool_names & catalog_tools, f"No catalog tool calls in {tool_names}"
    assert tool_names & knowledge_tools, f"No knowledge tool calls in {tool_names}"


class TestToolFailureSemantics:
    """Failure must NOT emit tool_completed."""

    @pytest.mark.asyncio
    async def test_reader_failure_no_completed(self, tmp_path, events, bundle):
        """When read_uploaded_file fails, only tool_started is emitted."""
        from app.agent.runtime import MockTutorialRuntime

        thread_id = "00000000-0000-4000-8000-000000000099"
        ws = SessionWorkspace.for_thread(
            thread_id=thread_id,
            base_upload=str(tmp_path / "up"),
            base_output=str(tmp_path / "out"),
        )
        ctx = SessionContext(thread_id=thread_id, workspace=ws)
        rt = MockTutorialRuntime(bundle, events)

        # Create a non-UTF-8 upload that will fail
        bad_file = ws.resolve_upload("bad.txt")
        bad_file.write_bytes(b"\xff\xfe\x00\x00")

        async with events.subscribe(thread_id) as sub:
            try:
                await rt.run(RuntimeRequest("test", ctx))
            except Exception:
                pass
            emitted = []
            while not sub.queue.empty():
                emitted.append(sub.queue.get_nowait())

        # Must have tool_started but NO tool_completed for read_uploaded_file
        reader_started = [
            e
            for e in emitted
            if e.data.get("tool_name") == "read_uploaded_file"
            and e.type == "tool_started"
        ]
        reader_completed = [
            e
            for e in emitted
            if e.data.get("tool_name") == "read_uploaded_file"
            and e.type == "tool_completed"
        ]
        assert len(reader_started) >= 1, "Expected tool_started for read_uploaded_file"
        assert len(reader_completed) == 0, "tool_completed emitted on failure!"


class TestPreciseEventPairs:
    """Every success tool has started → call → completed ordering."""

    @pytest.mark.asyncio
    async def test_tool_started_before_call_before_completed(self, tmp_path, events):
        """Combined trace: events + provider calls interleaved.
        Asserts started:X -> call:X.method -> completed:X for each tool."""
        from app.agent.runtime import MockTutorialRuntime, RuntimeRequest
        from app.api.context import SessionContext
        from app.providers.contracts import (
            KnowledgeAnswer,
            ProviderBundle,
            QueryResult,
            SearchResult,
            TableInfo,
        )

        trace: list[str] = []

        class SpyWeb:
            def search(self, query, *, max_results=5):
                trace.append("call:web.search")
                return SearchResult(query=query, hits=())

        class SpyCatalog:
            def list_tables(self):
                trace.append("call:catalog.list_tables")
                return (TableInfo("drugs"),)

            def describe_table(self, tn):
                trace.append("call:catalog.describe_table")
                return QueryResult(columns=("id", "name"), rows=(), truncated=False)

            def preview_table(self, tn, *, limit=20):
                trace.append("call:catalog.preview_table")
                return QueryResult(columns=("id", "name"), rows=(), truncated=False)

            def execute_readonly(self, q, *, limit=100):
                trace.append("call:catalog.execute_readonly")
                return QueryResult(columns=("id",), rows=(), truncated=False)

        class SpyKnowledge:
            def list_assistants(self):
                trace.append("call:knowledge.list_assistants")
                from app.providers.contracts import KnowledgeAssistant

                return (KnowledgeAssistant("a", "d", ()),)

            def ask(self, an, q):
                trace.append("call:knowledge.ask")
                return KnowledgeAnswer(assistant_name=an, answer="ok")

        bundle = ProviderBundle(
            web=SpyWeb(),
            catalog=SpyCatalog(),
            knowledge=SpyKnowledge(),
            web_mode="mock",
            catalog_mode="mock",
            knowledge_mode="mock",
        )
        rt = MockTutorialRuntime(bundle, events)
        tid = "00000000-0000-4000-8000-000000000055"

        from app.tools.files import SessionWorkspace

        ws = SessionWorkspace.for_thread(
            thread_id=tid,
            base_upload=str(tmp_path / "up-spy"),
            base_output=str(tmp_path / "out-spy"),
        )
        ctx = SessionContext(thread_id=tid, workspace=ws)

        # Patch events.emit to record into trace
        orig_emit = events.emit

        def _tracing_emit(thread_id, event_type, message, data=None):
            tn = (data or {}).get("tool_name", "")
            if tn:
                trace.append(f"{event_type}:{tn}")
            return orig_emit(thread_id, event_type, message, data)

        events.emit = _tracing_emit  # type: ignore[method-assign]

        # Patch report writers to record calls into trace
        import app.agent.runtime as _rt

        _orig_md = _rt.generate_markdown_report
        _orig_pdf = _rt.generate_pdf_report

        def _md_trace(content):
            trace.append("call:generate_markdown_report")
            return _orig_md(content)

        def _pdf_trace(content):
            trace.append("call:generate_pdf_report")
            return _orig_pdf(content)

        _rt.generate_markdown_report = _md_trace  # type: ignore[assignment]
        _rt.generate_pdf_report = _pdf_trace  # type: ignore[assignment]

        async with events.subscribe(tid):
            await rt.run(RuntimeRequest("test", ctx))

        # Restore
        _rt.generate_markdown_report = _orig_md  # type: ignore[assignment]
        _rt.generate_pdf_report = _orig_pdf  # type: ignore[assignment]

        # Verify strict ordering: started -> call -> completed for each domain
        def _assert_triple(st: str, call: str, comp: str):
            si = trace.index(st)
            ci = trace.index(call)
            ei = trace.index(comp)
            assert si < ci < ei, f"Order wrong: {st}@{si} -> {call}@{ci} -> {comp}@{ei}"

        _assert_triple(
            "tool_started:internet_search",
            "call:web.search",
            "tool_completed:internet_search",
        )
        _assert_triple(
            "tool_started:list_sql_tables",
            "call:catalog.list_tables",
            "tool_completed:list_sql_tables",
        )
        _assert_triple(
            "tool_started:preview_table",
            "call:catalog.preview_table",
            "tool_completed:preview_table",
        )
        _assert_triple(
            "tool_started:execute_readonly_query",
            "call:catalog.execute_readonly",
            "tool_completed:execute_readonly_query",
        )
        _assert_triple(
            "tool_started:list_knowledge_assistants",
            "call:knowledge.list_assistants",
            "tool_completed:list_knowledge_assistants",
        )
        _assert_triple(
            "tool_started:ask_knowledge_assistant",
            "call:knowledge.ask",
            "tool_completed:ask_knowledge_assistant",
        )
        _assert_triple(
            "tool_started:generate_markdown_report",
            "call:generate_markdown_report",
            "tool_completed:generate_markdown_report",
        )
        _assert_triple(
            "tool_started:generate_pdf_report",
            "call:generate_pdf_report",
            "tool_completed:generate_pdf_report",
        )

        # No duplicate: each tool name exactly 1 pair
        for tn in (
            "internet_search",
            "list_sql_tables",
            "preview_table",
            "execute_readonly_query",
            "list_knowledge_assistants",
            "ask_knowledge_assistant",
            "generate_markdown_report",
            "generate_pdf_report",
        ):
            s_count = sum(1 for x in trace if x == f"tool_started:{tn}")
            c_count = sum(1 for x in trace if x == f"tool_completed:{tn}")
            assert s_count == 1, f"{tn}: {s_count} start events"
            assert c_count == 1, f"{tn}: {c_count} completed events"


class TestAgentEventPayload:
    """agent events carry agent_name."""

    @pytest.mark.asyncio
    async def test_agent_events_have_agent_name(
        self, runtime, workspace, context, events
    ):
        async with events.subscribe(THREAD_ID) as sub:
            await runtime.run(RuntimeRequest("test", context))
            emitted = []
            while not sub.queue.empty():
                emitted.append(sub.queue.get_nowait())

        for e in emitted:
            if e.type in ("agent_started", "agent_completed"):
                assert "agent_name" in e.data, f"{e.type} missing agent_name: {e.data}"
                assert isinstance(e.data["agent_name"], str)
                assert len(e.data["agent_name"]) > 0

    @pytest.mark.asyncio
    async def test_no_task_lifecycle_events(self, runtime, workspace, context, events):
        async with events.subscribe(THREAD_ID) as sub:
            await runtime.run(RuntimeRequest("test", context))
            emitted = []
            while not sub.queue.empty():
                emitted.append(sub.queue.get_nowait())

        forbidden = {"task_started", "task_completed", "task_cancelled", "task_failed"}
        found = [e for e in emitted if e.type in forbidden]
        assert not found, f"Task events leaked: {[(e.type, e.message) for e in found]}"


class TestFakeGraphArtifactDedup:
    """DeepAgentsTutorialRuntime with fake graph stream — artifact dedup."""

    @pytest.mark.asyncio
    async def test_wrappers_generated_both_reports_runtime_skips_compensation(
        self, tmp_path
    ):
        """Pre-emit wrapper artifacts, stream _tool names.
        Runtime must NOT compensate; each artifact exactly once."""
        from unittest.mock import AsyncMock, patch

        from app.agent.runtime import DeepAgentsTutorialRuntime

        fake_graph = AsyncMock()

        async def _fake_astream(*args, **kwargs):
            yield {
                "tools": {
                    "messages": [
                        _FakeMsg("generate_markdown_report_tool", "md done"),
                        _FakeMsg("generate_pdf_report_tool", "pdf done"),
                    ]
                }
            }

        fake_graph.astream = _fake_astream

        bundle = _bundle()
        events = InMemoryEventBus()
        rt = DeepAgentsTutorialRuntime(fake_graph, bundle, events)

        ws = SessionWorkspace.for_thread(
            thread_id=THREAD_ID,
            base_upload=str(tmp_path / "up-dedup"),
            base_output=str(tmp_path / "out-dedup"),
        )
        ctx = SessionContext(thread_id=THREAD_ID, workspace=ws)

        with patch("app.agent.runtime.generate_markdown_report") as mock_md:
            with patch("app.agent.runtime.generate_pdf_report") as mock_pdf:
                async with events.subscribe(THREAD_ID) as sub:
                    # Pre-emit wrapper artifact_created events
                    events.emit(
                        THREAD_ID,
                        "artifact_created",
                        "tutorial-report.md",
                        {
                            "path": "tutorial-report.md",
                            "name": "tutorial-report.md",
                            "media_type": "text/markdown",
                        },
                    )
                    events.emit(
                        THREAD_ID,
                        "artifact_created",
                        "tutorial-report.pdf",
                        {
                            "path": "tutorial-report.pdf",
                            "name": "tutorial-report.pdf",
                            "media_type": "application/pdf",
                        },
                    )
                    await rt.run(RuntimeRequest("test", ctx))
                    emitted = []
                    while not sub.queue.empty():
                        emitted.append(sub.queue.get_nowait())

        mock_md.assert_not_called()
        mock_pdf.assert_not_called()

        md_events = [
            e
            for e in emitted
            if e.type == "artifact_created"
            and e.data.get("path") == "tutorial-report.md"
        ]
        pdf_events = [
            e
            for e in emitted
            if e.type == "artifact_created"
            and e.data.get("path") == "tutorial-report.pdf"
        ]
        assert len(md_events) == 1, f"Expected 1 md artifact, got {len(md_events)}"
        assert len(pdf_events) == 1, f"Expected 1 pdf artifact, got {len(pdf_events)}"
        for evt in md_events + pdf_events:
            assert not evt.data["path"].startswith("/")
            assert evt.data["name"] in (
                "tutorial-report.md",
                "tutorial-report.pdf",
            )
            if evt.data["path"] == "tutorial-report.md":
                assert evt.data["media_type"] == "text/markdown"
            if evt.data["path"] == "tutorial-report.pdf":
                assert evt.data["media_type"] == "application/pdf"


class _FakeMsg:
    def __init__(self, name, content, type=""):
        self.name = name
        self.content = content
        self.type = type


FAKE_KEY = "sk-b6-secret-12345"  # pragma: allowlist secret
RAW_MARKER = "raw-b6-payload-marker"
PATH_MARKER = "/var/b6-cache/raw-response.json"
SENSITIVE_TEXT = f"denied key={FAKE_KEY} payload={RAW_MARKER} path={PATH_MARKER}"


def _sensitive_error() -> RuntimeError:
    return RuntimeError(SENSITIVE_TEXT)


class _FailingWeb:
    def search(self, query: str, *, max_results: int = 5):
        raise _sensitive_error()


class _FailingCatalog:
    def list_tables(self):
        return (TableInfo("drugs"),)

    def describe_table(self, table_name):
        raise _sensitive_error()

    def preview_table(self, table_name, *, limit=20):
        raise _sensitive_error()

    def execute_readonly(self, query, *, limit=100):
        raise _sensitive_error()


class _FailingKnowledge:
    def list_assistants(self):
        return (KnowledgeAssistant("a", "d", ()),)

    def ask(self, assistant_name, question):
        raise _sensitive_error()


def _failing_bundle(web=None, catalog=None, knowledge=None) -> ProviderBundle:
    return ProviderBundle(
        web=web or MockWebProvider(),
        catalog=catalog or MockCatalogProvider(),
        knowledge=knowledge or MockKnowledgeProvider(),
        web_mode="mock",
        catalog_mode="mock",
        knowledge_mode="mock",
    )


async def _run_failing(rt, ctx, events, tid):
    async with events.subscribe(tid) as sub:
        with pytest.raises(RuntimeError):
            await rt.run(RuntimeRequest("test", ctx))
        emitted = []
        while not sub.queue.empty():
            emitted.append(sub.queue.get_nowait())
    return emitted


def _assert_events_clean(emitted) -> None:
    for e in emitted:
        assert FAKE_KEY not in e.message, f"credential leaked in event: {e!r}"
        assert RAW_MARKER not in e.message, f"raw payload leaked in event: {e!r}"
        assert PATH_MARKER not in e.message, f"absolute path leaked in event: {e!r}"
        assert FAKE_KEY not in str(e.data), f"credential leaked in data: {e!r}"
        assert RAW_MARKER not in str(e.data), f"raw payload leaked in data: {e!r}"
        assert PATH_MARKER not in str(e.data), f"absolute path leaked in data: {e!r}"


class TestProviderFailureRedaction:
    @pytest.mark.asyncio
    async def test_failing_web_events_clean_no_terminal_no_report(
        self, tmp_path, events
    ):
        rt = MockTutorialRuntime(_failing_bundle(web=_FailingWeb()), events)
        tid = "00000000-0000-4000-8000-0000000000a1"
        ws = SessionWorkspace.for_thread(
            thread_id=tid,
            base_upload=str(tmp_path / "up"),
            base_output=str(tmp_path / "out"),
        )
        ctx = SessionContext(thread_id=tid, workspace=ws)
        emitted = await _run_failing(rt, ctx, events, tid)

        _assert_events_clean(emitted)
        terminal = {"task_started", "task_completed", "task_cancelled", "task_failed"}
        assert not terminal & {e.type for e in emitted}, [e.type for e in emitted]
        assert [e.type for e in emitted].count("tool_started") == 1
        assert [e.type for e in emitted].count("tool_completed") == 0
        assert not list(ws.output_dir.glob("tutorial-report.*"))

    @pytest.mark.asyncio
    async def test_failing_catalog_events_clean_and_no_fake_completed(
        self, tmp_path, events
    ):
        rt = MockTutorialRuntime(_failing_bundle(catalog=_FailingCatalog()), events)
        tid = "00000000-0000-4000-8000-0000000000a2"
        ws = SessionWorkspace.for_thread(
            thread_id=tid,
            base_upload=str(tmp_path / "up"),
            base_output=str(tmp_path / "out"),
        )
        ctx = SessionContext(thread_id=tid, workspace=ws)
        emitted = await _run_failing(rt, ctx, events, tid)

        _assert_events_clean(emitted)
        started = {e.data.get("tool_name") for e in emitted if e.type == "tool_started"}
        completed = {
            e.data.get("tool_name") for e in emitted if e.type == "tool_completed"
        }
        assert "preview_table" in started
        assert "preview_table" not in completed
        assert not list(ws.output_dir.glob("tutorial-report.*"))

    @pytest.mark.asyncio
    async def test_failing_knowledge_ask_events_clean(self, tmp_path, events):
        rt = MockTutorialRuntime(_failing_bundle(knowledge=_FailingKnowledge()), events)
        tid = "00000000-0000-4000-8000-0000000000a3"
        ws = SessionWorkspace.for_thread(
            thread_id=tid,
            base_upload=str(tmp_path / "up"),
            base_output=str(tmp_path / "out"),
        )
        ctx = SessionContext(thread_id=tid, workspace=ws)
        emitted = await _run_failing(rt, ctx, events, tid)

        _assert_events_clean(emitted)
        started = {e.data.get("tool_name") for e in emitted if e.type == "tool_started"}
        completed = {
            e.data.get("tool_name") for e in emitted if e.type == "tool_completed"
        }
        assert "ask_knowledge_assistant" in started
        assert "ask_knowledge_assistant" not in completed
        assert not list(ws.output_dir.glob("tutorial-report.*"))


class TestDeepAgentsReportRedaction:
    @pytest.mark.asyncio
    async def test_failed_tool_content_not_echoed_into_compensation_report(
        self, tmp_path
    ):
        from unittest.mock import AsyncMock

        from app.agent.runtime import DeepAgentsTutorialRuntime

        fake_graph = AsyncMock()

        async def _fake_astream(*args, **kwargs):
            yield {"tools": {"messages": [_FakeMsg("some_tool", SENSITIVE_TEXT)]}}
            yield {
                "agent": {
                    "messages": [
                        _FakeMsg(
                            "tutorial-research-agent",
                            "Final clean summary",
                            type="ai",
                        )
                    ]
                }
            }

        fake_graph.astream = _fake_astream
        rt = DeepAgentsTutorialRuntime(fake_graph, _bundle(), InMemoryEventBus())
        tid = "00000000-0000-4000-8000-0000000000a4"
        ws = SessionWorkspace.for_thread(
            thread_id=tid,
            base_upload=str(tmp_path / "up"),
            base_output=str(tmp_path / "out"),
        )
        ctx = SessionContext(thread_id=tid, workspace=ws)
        result = await rt.run(RuntimeRequest("test", ctx))

        assert FAKE_KEY not in result.answer
        assert RAW_MARKER not in result.answer
        assert "Final clean summary" in result.answer

        md = ws.resolve_output("tutorial-report.md")
        content = md.read_text()
        assert FAKE_KEY not in content
        assert RAW_MARKER not in content
        assert PATH_MARKER not in content
        assert "Final clean summary" in content


class TestKnowledgeToolEventStability:
    @pytest.mark.asyncio
    async def test_ask_tool_events_never_carry_assistant_name(self, events):
        from app.tools.knowledge import create_knowledge_tools

        class _QuietKnowledge:
            def list_assistants(self):
                return ()

            def ask(self, assistant_name, question):
                return KnowledgeAnswer(assistant_name=assistant_name, answer="ok")

        ask_tool = create_knowledge_tools(_QuietKnowledge(), events)[1]
        config = {"configurable": {"thread_id": THREAD_ID}}
        async with events.subscribe(THREAD_ID) as sub:
            await ask_tool.ainvoke(
                {"an": f"assistant-{FAKE_KEY}", "q": "q"}, config=config
            )
            emitted = []
            while not sub.queue.empty():
                emitted.append(sub.queue.get_nowait())

        assert emitted, "expected paired tool events"
        for e in emitted:
            assert FAKE_KEY not in e.message
            assert e.message == "ask_knowledge_assistant"
