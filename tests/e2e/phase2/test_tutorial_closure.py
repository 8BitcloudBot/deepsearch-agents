"""E2E: Full API closure — HTTP endpoints + event verification.

Uses TestClient for all HTTP endpoints. Event verification via event bus
because Starlette's sync TestClient cannot support concurrent WS+HTTP
from separate threads. WS behavior is covered by test_websocket_flow.py.
"""

import asyncio

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


@pytest.fixture
def events():
    return InMemoryEventBus()


@pytest.fixture
def app(events):
    from app.agent.runtime import MockTutorialRuntime
    from app.settings import Phase2Settings

    bundle = ProviderBundle(
        web=MockWebProvider(),
        catalog=MockCatalogProvider(),
        knowledge=MockKnowledgeProvider(),
        web_mode="mock",
        catalog_mode="mock",
        knowledge_mode="mock",
    )
    runtime = MockTutorialRuntime(bundle, events)
    return create_app(
        settings=Phase2Settings(),
        bundle=bundle,
        runtime=runtime,
        events=events,
    )


@pytest.mark.asyncio
async def test_full_mock_closure(app, events):
    """Upload → task start → events → files → download. All via real API."""
    import time

    tid = "00000000-0000-4000-8000-0000000000e1"
    client = TestClient(app)

    # 1. POST /api/upload
    r = client.post(
        "/api/upload",
        data={"thread_id": tid},
        files={
            "files": (
                "constraints.md",
                b"# Constraint: keep it short.",
                "text/markdown",
            )
        },
    )
    assert r.status_code == 200
    assert r.json()["status"] == "uploaded"

    # 2. Subscribe to events, then POST /api/task via async client
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    collected: list = []

    async with events.subscribe(tid) as sub:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r2 = await ac.post(
                "/api/task",
                json={"query": "research aspirin", "thread_id": tid},
            )
            assert r2.status_code == 202

        # Drain events
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                evt = await asyncio.wait_for(
                    sub.queue.get(), max(0, deadline - time.time())
                )
                collected.append(evt)
                if evt.type in (
                    "task_completed",
                    "task_cancelled",
                    "task_failed",
                ):
                    break
            except TimeoutError:
                break

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
    assert len(terminals) == 1
    assert terminals[0].type == "task_completed"

    # 5. GET /api/files
    r = client.get("/api/files", params={"thread_id": tid})
    assert r.status_code == 200
    fnames = {f["name"] for f in r.json()["files"]}
    assert "tutorial-report.md" in fnames
    assert "tutorial-report.pdf" in fnames

    # 6. GET /api/download Markdown
    r = client.get(
        "/api/download",
        params={"thread_id": tid, "path": "tutorial-report.md"},
    )
    assert r.status_code == 200
    md = r.text
    assert len(md) > 50
    assert "constraint" in md.lower() or "Constraint" in md
    assert "web_mode" in md
    assert "catalog_mode" in md
    assert "knowledge_mode" in md

    # 7. GET /api/download PDF
    r = client.get(
        "/api/download",
        params={"thread_id": tid, "path": "tutorial-report.pdf"},
    )
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"
