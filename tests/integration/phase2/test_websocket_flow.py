"""Integration: WebSocket tests using Starlette TestClient."""

import json

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


def test_ws_ping_pong(client):
    tid = "00000000-0000-4000-8000-0000000000d2"
    with client.websocket_connect(f"/ws/{tid}") as ws:
        ws.send_text(json.dumps({"type": "ping"}))
        data = json.loads(ws.receive_text())
        assert data["type"] == "pong"


def test_ws_subscription_before_accept(client, events):
    """Emit event → WS receives it after connection."""
    tid = "00000000-0000-4000-8000-0000000000d1"
    with client.websocket_connect(f"/ws/{tid}") as ws:
        events.emit(tid, "tool_started", "s", {"tool_name": "t"})
        data = json.loads(ws.receive_text())
        assert data["type"] == "tool_started"


def test_ws_thread_isolation(client, events):
    tid_a = "00000000-0000-4000-8000-0000000000d4"
    tid_b = "00000000-0000-4000-8000-0000000000d5"

    with client.websocket_connect(f"/ws/{tid_a}") as ws_a:
        with client.websocket_connect(f"/ws/{tid_b}") as ws_b:
            events.emit(tid_a, "tool_started", "a", {"tool_name": "t"})
            events.emit(tid_b, "tool_started", "b", {"tool_name": "t"})
            assert json.loads(ws_a.receive_text())["message"] == "a"
            assert json.loads(ws_b.receive_text())["message"] == "b"


def test_ws_high_volume_ok(client, events):
    """Connection survives many events."""
    tid = "00000000-0000-4000-8000-0000000000d7"
    with client.websocket_connect(f"/ws/{tid}") as ws:
        for i in range(20):
            events.emit(tid, "tool_started", f"m{i}", {"tool_name": "t"})
        for _ in range(10):
            data = json.loads(ws.receive_text())
            assert data["type"] == "tool_started"
