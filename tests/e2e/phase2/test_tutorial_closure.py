"""E2E: Full tutorial closure — upload, task, WebSocket, download."""

import time

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
        settings=Phase2Settings(),
        bundle=bundle,
        runtime=runtime,
        events=events,
    )
    return TestClient(app)


@pytest.mark.asyncio
async def test_full_mock_closure(client, events):
    """Upload, start task, verify events via bus, list/download reports."""
    import asyncio

    tid = "00000000-0000-4000-8000-0000000000e1"

    # 1. Upload
    resp = client.post(
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
    assert resp.status_code == 200
    assert resp.json()["status"] == "uploaded"

    # 2. Start task with subscription
    collected = []
    async with events.subscribe(tid) as sub:
        # Use httpx async client for the task POST
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(
            app=client._transport.app  # type: ignore[union-attr]
        )
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/task",
                json={"query": "research aspirin", "thread_id": tid},
            )
            assert resp.status_code == 202

        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                evt = await asyncio.wait_for(
                    sub.queue.get(),
                    max(0, deadline - time.time()),
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

    # 3. Provider tools
    tool_names = {e.data.get("tool_name", "") for e in collected}
    assert tool_names & {
        "internet_search",
        "list_sql_tables",
        "ask_knowledge_assistant",
    }, f"Missing: {tool_names}"

    # 4. Files
    resp = client.get("/api/files", params={"thread_id": tid})
    assert resp.status_code == 200
    fnames = {f["name"] for f in resp.json()["files"]}
    assert "tutorial-report.md" in fnames
    assert "tutorial-report.pdf" in fnames

    # 5. Download
    resp = client.get(
        "/api/download",
        params={"thread_id": tid, "path": "tutorial-report.md"},
    )
    assert resp.status_code == 200
    assert len(resp.text) > 50
    assert "constraint" in resp.text.lower() or "Constraint" in resp.text
    assert "mock" in resp.text.lower() or "Provider" in resp.text
