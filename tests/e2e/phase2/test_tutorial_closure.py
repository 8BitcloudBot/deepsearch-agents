"""E2E: Full tutorial closure — upload, task, events, files, download."""

import asyncio
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
        settings=Phase2Settings(), bundle=bundle, runtime=runtime, events=events
    )
    return TestClient(app)


@pytest.mark.asyncio
async def test_full_mock_closure(client, events, tmp_path):
    """Upload, start task with subscription, verify all reports."""
    tid = "00000000-0000-4000-8000-0000000000e1"

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

    async with events.subscribe(tid) as sub:
        client.post("/api/task", json={"query": "research aspirin", "thread_id": tid})
        collected = []
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

    tool_names = {e.data.get("tool_name", "") for e in collected}
    assert "internet_search" in tool_names
    assert tool_names & {"list_sql_tables", "preview_table"}
    # knowledge tools may appear (list_knowledge_assistants)
    has_knowledge = bool(
        tool_names & {"list_knowledge_assistants", "ask_knowledge_assistant"}
    )
    assert has_knowledge or "list_knowledge_assistants" in tool_names

    r = client.get("/api/files", params={"thread_id": tid})
    assert r.status_code == 200
    fnames = {f["name"] for f in r.json()["files"]}
    assert "tutorial-report.md" in fnames
    assert "tutorial-report.pdf" in fnames

    r = client.get(
        "/api/download", params={"thread_id": tid, "path": "tutorial-report.md"}
    )
    assert r.status_code == 200
    content = r.text
    assert len(content) > 50
    assert "constraint" in content.lower() or "Constraint" in content
    assert "web_mode" in content or "mock" in content.lower()


def test_cross_thread_isolation(client):
    tid_a = "00000000-0000-4000-8000-0000000000e2"
    tid_b = "00000000-0000-4000-8000-0000000000e3"
    client.post(
        "/api/upload",
        data={"thread_id": tid_a},
        files={"files": ("a.txt", b"a", "text/plain")},
    )
    r = client.get("/api/files", params={"thread_id": tid_b})
    assert r.json()["files"] == []
