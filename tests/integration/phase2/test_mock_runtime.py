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
