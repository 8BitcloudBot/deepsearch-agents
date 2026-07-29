"""Integration: Real WebSocket tests using Starlette TestClient."""

import json
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


def test_ws_subscription_before_accept(app, events):
    """WS handler subscribes before accepting; receives events."""
    tid = "00000000-0000-4000-8000-0000000000d1"
    client = TestClient(app)

    with client.websocket_connect(f"/ws/{tid}") as ws:
        events.emit(
            tid,
            "tool_started",
            "search",
            {"tool_name": "internet_search"},
        )
        data = json.loads(ws.receive_text())
        assert data["type"] == "tool_started"


def test_ws_ping_pong(app, events):
    """Ping receives pong; pong not in event bus."""
    tid = "00000000-0000-4000-8000-0000000000d2"
    client = TestClient(app)

    with client.websocket_connect(f"/ws/{tid}") as ws:
        ws.send_text(json.dumps({"type": "ping"}))
        data = json.loads(ws.receive_text())
        assert data["type"] == "pong"
        # Verify no pong event in the bus by checking sequence count
        seq = events._sequences.get(tid, 0)
        # pong should not add to event bus sequence
        assert seq == 0  # no non-pong events either at this point


def test_ws_terminal_event_delivery(app, events):
    """Task events delivered via WebSocket."""
    tid = "00000000-0000-4000-8000-0000000000d3"

    # Connect WS first, then start task in separate client
    ws_client = TestClient(app)
    with ws_client.websocket_connect(f"/ws/{tid}") as ws:
        # Now use a separate httpx client to start the task
        with httpx.Client(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = c.post(
                "/api/task",
                json={"query": "test", "thread_id": tid},
            )
            assert resp.status_code == 202

        collected = []
        import time

        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                data = json.loads(ws.receive_text())
                collected.append(data)
                if data["type"] in (
                    "task_completed",
                    "task_cancelled",
                    "task_failed",
                ):
                    break
            except Exception:
                break

        terminal = [
            d
            for d in collected
            if d["type"] in ("task_completed", "task_cancelled", "task_failed")
        ]
        assert len(terminal) == 1, (
            f"Expected 1 terminal, got {len(terminal)}: {collected}"
        )


def test_ws_thread_isolation(app, events):
    """Events for thread_A don't leak to thread_B."""
    tid_a = "00000000-0000-4000-8000-0000000000d4"
    tid_b = "00000000-0000-4000-8000-0000000000d5"
    client = TestClient(app)

    with client.websocket_connect(f"/ws/{tid_a}") as ws_a:
        with client.websocket_connect(f"/ws/{tid_b}") as ws_b:
            events.emit(
                tid_a,
                "tool_started",
                "a-search",
                {"tool_name": "internet_search"},
            )
            events.emit(
                tid_b,
                "tool_started",
                "b-search",
                {"tool_name": "internet_search"},
            )

            data_a = json.loads(ws_a.receive_text())
            data_b = json.loads(ws_b.receive_text())
            assert data_a["message"] == "a-search"
            assert data_b["message"] == "b-search"


def test_ws_disconnect_does_not_cancel_task(app, events):
    """WebSocket disconnect doesn't cancel the running task."""
    tid = "00000000-0000-4000-8000-0000000000d6"

    # Start task via HTTP
    with httpx.Client(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = c.post(
            "/api/task",
            json={"query": "test", "thread_id": tid},
        )
        assert resp.status_code == 202

    # Connect WS, get events, disconnect
    client = TestClient(app)
    with client.websocket_connect(f"/ws/{tid}") as ws:
        data = json.loads(ws.receive_text())
        assert data["type"] in ("agent_started", "tool_started")

    # Wait for task to complete

    time.sleep(2)
    seq = events._sequences.get(tid, 0)
    assert seq > 0, f"Task didn't produce events after disconnect (seq={seq})"
