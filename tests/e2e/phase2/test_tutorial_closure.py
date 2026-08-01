"""E2E: Full API closure — upload, task, events, files, download.

Uses sync TestClient for upload/files/download. Task POST and event
collection via async httpx + event bus subscription (same events
delivered to WebSocket). WS behavior verified by test_websocket_flow.py.
"""

import asyncio
import time

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from app.api.events import InMemoryEventBus
from app.api.server import create_app
from app.providers.contracts import ProviderBundle
from app.providers.mock import (
    MockCatalogProvider,
    MockKnowledgeProvider,
    MockWebProvider,
)

UNIQUE_MARKER = "UNIQUE-E2E-CONSTRAINT-20260801"


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
        settings=Phase2Settings(), bundle=bundle, runtime=runtime, events=events
    )


@pytest.mark.asyncio
async def test_full_api_closure(app, events, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tid = "00000000-0000-4000-8000-0000000000e1"
    client = TestClient(app)

    # 1. Upload via sync TestClient
    r = client.post(
        "/api/upload",
        data={"thread_id": tid},
        files={
            "files": (
                "constraints.md",
                f"# {UNIQUE_MARKER}\n\nKeep it short.".encode(),
                "text/markdown",
            )
        },
    )
    assert r.status_code == 200

    # 2. Start task via async httpx + collect events via event bus
    transport = ASGITransport(app=app)
    collected: list = []

    async with events.subscribe(tid) as sub:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r2 = await ac.post(
                "/api/task", json={"query": "research aspirin", "thread_id": tid}
            )
            assert r2.status_code == 202

        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                evt = await asyncio.wait_for(
                    sub.queue.get(), max(0, deadline - time.time())
                )
                collected.append(evt)
                if evt.type in ("task_completed", "task_cancelled", "task_failed"):
                    break
            except TimeoutError:
                break

    # 3. Verify providers
    tool_names = {e.data.get("tool_name", "") for e in collected}
    assert "internet_search" in tool_names, f"web: {sorted(tool_names)}"
    assert "list_sql_tables" in tool_names, f"catalog: {sorted(tool_names)}"
    assert "list_knowledge_assistants" in tool_names, f"knowledge: {sorted(tool_names)}"
    terminals = [
        e
        for e in collected
        if e.type in ("task_completed", "task_cancelled", "task_failed")
    ]
    assert len(terminals) == 1
    assert terminals[0].type == "task_completed"

    # 4. Files + download
    r = client.get("/api/files", params={"thread_id": tid})
    assert r.status_code == 200
    fnames = {f["name"] for f in r.json()["files"]}
    assert "tutorial-report.md" in fnames
    assert "tutorial-report.pdf" in fnames

    r = client.get(
        "/api/download", params={"thread_id": tid, "path": "tutorial-report.md"}
    )
    assert r.status_code == 200
    md = r.text
    assert len(md) > 50
    assert UNIQUE_MARKER in md
    assert "web_mode" in md
    assert "catalog_mode" in md
    assert "knowledge_mode" in md

    r = client.get(
        "/api/download", params={"thread_id": tid, "path": "tutorial-report.pdf"}
    )
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"
