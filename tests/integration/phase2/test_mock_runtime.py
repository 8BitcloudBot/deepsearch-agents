"""Integration: deterministic mock runtime with workspace and events."""

import asyncio
from pathlib import Path

import pytest

from app.agent.runtime import MockTutorialRuntime, RuntimeRequest
from app.api.context import SessionContext
from app.api.events import InMemoryEventBus
from app.providers.contracts import ProviderBundle
from app.providers.mock import (
    MockCatalogProvider,
    MockKnowledgeRetriever,
    MockWebProvider,
)
from app.tools.files import SessionWorkspace

THREAD_ID = "00000000-0000-4000-8000-000000000001"

FAKE_KEY = "sk-b6-secret-12345"  # pragma: allowlist secret
RAW_MARKER = "raw-b6-payload-marker"
PATH_MARKER = "/var/b6-cache/raw-response.json"


class _FailingWeb:
    def search(self, query: str, *, max_results: int = 5):
        raise RuntimeError(
            f"denied key={FAKE_KEY} payload={RAW_MARKER} path={PATH_MARKER}"
        )


def _bundle() -> ProviderBundle:
    return ProviderBundle(
        web=MockWebProvider(),
        catalog=MockCatalogProvider(),
        knowledge=MockKnowledgeRetriever(),
        web_mode="mock",
        catalog_mode="mock",
        knowledge_mode="mock",
    )


@pytest.fixture
def bundle():
    return _bundle()


@pytest.fixture
def events():
    return InMemoryEventBus()


@pytest.fixture
def workspace(tmp_path: Path):
    return SessionWorkspace.for_thread(
        thread_id=THREAD_ID,
        base_upload=str(tmp_path / "updated"),
        base_output=str(tmp_path / "output"),
    )


@pytest.fixture
def context(workspace):
    return SessionContext(thread_id=THREAD_ID, workspace=workspace)


@pytest.fixture
def runtime(bundle, events):
    return MockTutorialRuntime(bundle, events)


@pytest.mark.asyncio
async def test_mock_runtime_full_flow(runtime, workspace, context, events):
    """Complete flow: subscribe, run, collect events, verify output."""
    async with events.subscribe(THREAD_ID) as sub:
        result = await runtime.run(
            RuntimeRequest("research aspirin and ibuprofen", context)
        )
        emitted = []
        while not sub.queue.empty():
            emitted.append(sub.queue.get_nowait())

    # Basic result shape
    assert isinstance(result.answer, str)
    assert len(result.answer) > 20
    assert result.artifacts == ("tutorial-report.md", "tutorial-report.pdf")

    # Events present
    event_types = {e.type for e in emitted}
    assert "agent_started" in event_types
    assert "agent_completed" in event_types
    assert "tool_started" in event_types
    assert "tool_completed" in event_types
    assert "artifact_created" in event_types

    # No task lifecycle leak
    assert (
        not {"task_started", "task_completed", "task_cancelled", "task_failed"}
        & event_types
    )

    # Files on disk
    md = workspace.resolve_output("tutorial-report.md")
    pdf = workspace.resolve_output("tutorial-report.pdf")
    assert md.exists()
    assert pdf.exists()

    # Markdown content
    content = md.read_text()
    assert len(content) > 50
    assert "mock" in content.lower() or "tutorial" in content.lower()

    # PDF is valid
    pdf_data = pdf.read_bytes()
    assert pdf_data.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_mock_runtime_concurrent_runs_independent(tmp_path, bundle, events):
    """Two runs with different thread_ids do not interfere."""
    from app.agent.runtime import MockTutorialRuntime

    rt = MockTutorialRuntime(bundle, events)

    async def _run(thread_id: str):
        ws = SessionWorkspace.for_thread(
            thread_id=thread_id,
            base_upload=str(tmp_path / "updated"),
            base_output=str(tmp_path / "output"),
        )
        ctx = SessionContext(thread_id=thread_id, workspace=ws)
        async with events.subscribe(thread_id) as _sub:
            return await rt.run(RuntimeRequest("test", ctx))

    r1, r2 = await asyncio.gather(
        _run("00000000-0000-4000-8000-000000000001"),
        _run("00000000-0000-4000-8000-000000000002"),
    )

    assert r1.answer != ""
    assert r2.answer != ""
    assert r1.artifacts == ("tutorial-report.md", "tutorial-report.pdf")
    assert r2.artifacts == ("tutorial-report.md", "tutorial-report.pdf")

    # Files are in separate directories
    ws1 = SessionWorkspace.for_thread(
        thread_id="00000000-0000-4000-8000-000000000001",
        base_upload=str(tmp_path / "updated"),
        base_output=str(tmp_path / "output"),
    )
    ws2 = SessionWorkspace.for_thread(
        thread_id="00000000-0000-4000-8000-000000000002",
        base_upload=str(tmp_path / "updated"),
        base_output=str(tmp_path / "output"),
    )
    assert ws1.resolve_output("tutorial-report.md") != ws2.resolve_output(
        "tutorial-report.md"
    )
    assert ws1.resolve_output("tutorial-report.md").read_text()
    assert ws2.resolve_output("tutorial-report.md").read_text()


@pytest.mark.asyncio
async def test_registry_active_cancel_mock_runtime(bundle, events, tmp_path):
    """TaskRegistry cancelling an active MockTutorialRuntime run emits one terminal."""
    from app.api.tasks import TaskRegistry

    reg = TaskRegistry(
        runtime=MockTutorialRuntime(bundle, events),
        events=events,
        base_upload=str(tmp_path / "upload"),
        base_output=str(tmp_path / "output"),
    )
    tid = "00000000-0000-4000-8000-0000000000ff"
    async with events.subscribe(tid) as sub:
        assert reg.start("research aspirin", thread_id=tid) == tid
        # Wait until the runtime is provably mid-run (agent_started is emitted
        # inside MockTutorialRuntime.run before any provider I/O).
        types = []
        while "agent_started" not in types:
            event = await asyncio.wait_for(sub.queue.get(), timeout=2.0)
            types.append(event.type)
        assert await reg.cancel(tid) == "cancelled"
        while not sub.queue.empty():
            types.append(sub.queue.get_nowait().type)
    assert types.count("task_cancelled") == 1
    assert not {"task_completed", "task_failed"} & set(types)
    assert types[0] == "task_started"
    assert reg.active_count == 0


@pytest.mark.asyncio
async def test_registry_failure_terminal_empty_events_clean_no_reports(
    bundle, events, tmp_path
):
    """Provider failure: task_failed carries an empty payload and no markers."""
    from app.api.tasks import TaskRegistry

    failing = ProviderBundle(
        web=_FailingWeb(),
        catalog=MockCatalogProvider(),
        knowledge=MockKnowledgeRetriever(),
        web_mode="mock",
        catalog_mode="mock",
        knowledge_mode="mock",
    )
    reg = TaskRegistry(
        runtime=MockTutorialRuntime(failing, events),
        events=events,
        base_upload=str(tmp_path / "upload"),
        base_output=str(tmp_path / "output"),
    )
    tid = "00000000-0000-4000-8000-0000000000b1"
    async with events.subscribe(tid) as sub:
        assert reg.start("research", thread_id=tid) == tid
        collected = []
        while "task_failed" not in [e.type for e in collected]:
            collected.append(await asyncio.wait_for(sub.queue.get(), timeout=2.0))
        while not sub.queue.empty():
            collected.append(sub.queue.get_nowait())

    failed = [e for e in collected if e.type == "task_failed"]
    assert len(failed) == 1
    assert failed[0].message == ""
    assert failed[0].data == {}
    for e in collected:
        assert FAKE_KEY not in e.message, f"credential leaked in event: {e!r}"
        assert RAW_MARKER not in e.message, f"raw payload leaked in event: {e!r}"
        assert PATH_MARKER not in e.message, f"absolute path leaked in event: {e!r}"
        assert FAKE_KEY not in str(e.data), f"credential leaked in data: {e!r}"
        assert RAW_MARKER not in str(e.data), f"raw payload leaked in data: {e!r}"
        assert PATH_MARKER not in str(e.data), f"absolute path leaked in data: {e!r}"
    assert reg.active_count == 0

    ws = SessionWorkspace.for_thread(
        thread_id=tid,
        base_upload=str(tmp_path / "upload"),
        base_output=str(tmp_path / "output"),
    )
    assert not list(ws.output_dir.glob("tutorial-report.*"))
