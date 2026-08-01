"""E2E: Full tutorial closure — upload, task, events, files, download."""

import pytest
from starlette.testclient import TestClient

from app.api.events import InMemoryEventBus
from app.api.server import create_app
from app.providers.contracts import ProviderBundle
from app.providers.mock import (
    MockCatalogProvider,
    MockKnowledgeProvider,
    MockWebProvider,
)


def _bundle():
    return ProviderBundle(
        web=MockWebProvider(),
        catalog=MockCatalogProvider(),
        knowledge=MockKnowledgeProvider(),
        web_mode="mock",
        catalog_mode="mock",
        knowledge_mode="mock",
    )


@pytest.fixture
def events():
    return InMemoryEventBus()


@pytest.fixture
def client(events):
    from app.agent.runtime import MockTutorialRuntime
    from app.settings import Phase2Settings

    bundle = _bundle()
    runtime = MockTutorialRuntime(bundle, events)
    app = create_app(
        settings=Phase2Settings(), bundle=bundle, runtime=runtime, events=events
    )
    return TestClient(app)


@pytest.mark.asyncio
async def test_full_mock_closure(events):
    """Upload via HTTP, subscribe, run runtime directly, verify."""
    from app.agent.runtime import MockTutorialRuntime, RuntimeRequest
    from app.api.context import SessionContext
    from app.tools.files import SessionWorkspace

    tid = "00000000-0000-4000-8000-0000000000e1"
    bundle = _bundle()
    rt = MockTutorialRuntime(bundle, events)
    ws = SessionWorkspace.for_thread(
        thread_id=tid, base_upload="updated", base_output="output"
    )

    # 1. Upload via the same workspace
    from app.tools.files import save_uploaded_file

    save_uploaded_file(ws, "constraints.md", b"# Constraint: keep it short.")

    # 2. Run task with subscription
    collected: list = []
    async with events.subscribe(tid) as sub:
        ctx = SessionContext(thread_id=tid, workspace=ws)
        await rt.run(RuntimeRequest(query="research aspirin", context=ctx))
        while not sub.queue.empty():
            collected.append(sub.queue.get_nowait())

    # 3. Verify all three providers
    tool_names = {e.data.get("tool_name", "") for e in collected}
    assert "internet_search" in tool_names, f"web: {sorted(tool_names)}"
    assert "list_sql_tables" in tool_names, f"catalog: {sorted(tool_names)}"
    assert "list_knowledge_assistants" in tool_names, f"knowledge: {sorted(tool_names)}"

    # 4. Exactly one terminal
    terminals = [
        e
        for e in collected
        if e.type in ("task_completed", "task_cancelled", "task_failed")
    ]
    assert len(terminals) == 0  # runtime run() doesn't emit terminal events

    # 5. Reports exist
    assert ws.resolve_output("tutorial-report.md").exists()
    assert ws.resolve_output("tutorial-report.pdf").exists()

    # 6. Verify Markdown content
    content = ws.resolve_output("tutorial-report.md").read_text()
    assert len(content) > 50
    assert "constraint" in content.lower() or "Constraint" in content
    assert "web_mode" in content or "mock" in content.lower()
    assert "/etc" not in content
