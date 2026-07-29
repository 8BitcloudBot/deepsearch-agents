"""E2E: Full tutorial closure — upload, task, WebSocket, download."""

import json
import threading
import time

import httpx
import pytest
from httpx import ASGITransport
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
def app(events):
    from app.agent.runtime import MockTutorialRuntime
    from app.settings import Phase2Settings

    bundle = _bundle()
    runtime = MockTutorialRuntime(bundle, events)
    return create_app(
        settings=Phase2Settings(),
        bundle=bundle,
        runtime=runtime,
        events=events,
    )


def test_full_mock_closure(app, events):
    """Upload constraints.md, start task, collect events via WS,
    list/download reports, verify content."""
    tid = "00000000-0000-4000-8000-0000000000e1"
    transport = ASGITransport(app=app)

    # 1. Upload to target thread
    with httpx.Client(transport=transport, base_url="http://test") as client:
        up_resp = client.post(
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
        assert up_resp.status_code == 200
        assert up_resp.json()["status"] == "uploaded"

    client_ws = TestClient(app)

    # 2. Start task in background thread
    def _start_task():
        with httpx.Client(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            resp = c.post(
                "/api/task",
                json={"query": "research aspirin", "thread_id": tid},
            )
            assert resp.status_code == 202

    th = threading.Thread(target=_start_task)
    th.start()
    time.sleep(0.1)

    # 3. Collect events via WebSocket
    with client_ws.websocket_connect(f"/ws/{tid}") as ws:
        collected = []
        try:
            while True:
                data = json.loads(ws.receive_text())
                collected.append(data)
                if data["type"] in (
                    "task_completed",
                    "task_cancelled",
                    "task_failed",
                ):
                    break
        except Exception:
            pass

    th.join()

    # 4. Assert provider tool coverage
    tool_names = {e.get("data", {}).get("tool_name", "") for e in collected}
    assert tool_names & {
        "internet_search",
        "list_sql_tables",
        "ask_knowledge_assistant",
    }, f"Missing provider tools: {tool_names}"

    # 5. List files
    with httpx.Client(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        files_resp = client.get(f"/api/files/{tid}")
        assert files_resp.status_code == 200
        fnames = {f["name"] for f in files_resp.json()["files"]}
        assert "tutorial-report.md" in fnames
        assert "tutorial-report.pdf" in fnames

        # 6. Download Markdown report
        dl_resp = client.get(f"/api/download/{tid}/tutorial-report.md")
        assert dl_resp.status_code == 200
        content = dl_resp.text
        assert len(content) > 50
        assert "constraint" in content.lower() or "Constraint" in content
        assert "mock" in content.lower() or "Provider" in content
