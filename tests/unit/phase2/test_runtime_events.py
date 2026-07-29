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

from app.agent.runtime import RuntimeRequest, RuntimeResult
from app.api.context import SessionContext
from app.api.events import InMemoryEventBus
from app.providers.contracts import ProviderBundle
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
    """Every success tool has exactly one started+completed pair."""

    @pytest.mark.asyncio
    async def test_each_success_tool_has_exact_pair(
        self, runtime, workspace, context, events
    ):
        """Each tool that succeeds must have exactly 1 started and 1 completed."""
        async with events.subscribe(THREAD_ID) as sub:
            await runtime.run(RuntimeRequest("test", context))
            emitted = []
            while not sub.queue.empty():
                emitted.append(sub.queue.get_nowait())

        tool_events = [
            e for e in emitted if e.type in ("tool_started", "tool_completed")
        ]
        by_name: dict[str, dict[str, int]] = {}
        for e in tool_events:
            tn = e.data.get("tool_name", "unknown")
            if tn not in by_name:
                by_name[tn] = {"started": 0, "completed": 0}
            by_name[tn][e.type[len("tool_") :]] += 1

        for tn, counts in by_name.items():
            assert counts["started"] == counts["completed"], (
                f"{tn}: started={counts['started']} != completed={counts['completed']}"
            )
            assert counts["started"] >= 1, f"{tn}: no events at all"


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
    async def test_wrappers_generated_both_reports_runtime_skips_compensation(self):
        """When stream contains tool messages named as actual tools,
        runtime must NOT call compensation writers."""
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
            base_upload="/tmp/up-dedup",
            base_output="/tmp/out-dedup",
        )
        ctx = SessionContext(thread_id=THREAD_ID, workspace=ws)

        with patch("app.agent.runtime.generate_markdown_report") as mock_md:
            with patch("app.agent.runtime.generate_pdf_report") as mock_pdf:
                async with events.subscribe(THREAD_ID) as sub:
                    await rt.run(RuntimeRequest("test", ctx))
                    emitted = []
                    while not sub.queue.empty():
                        emitted.append(sub.queue.get_nowait())

        # Compensation writers must NOT be called
        mock_md.assert_not_called()
        mock_pdf.assert_not_called()

        # Check that runtime did NOT generate duplicate artifacts
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
        assert len(md_events) == 0, f"Runtime compensated md artifact: {len(md_events)}"
        assert len(pdf_events) == 0, (
            f"Runtime compensated pdf artifact: {len(pdf_events)}"
        )


class _FakeMsg:
    def __init__(self, name, content):
        self.name = name
        self.content = content
