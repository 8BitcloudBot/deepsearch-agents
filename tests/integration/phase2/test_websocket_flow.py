"""Integration: WebSocket tests using Starlette TestClient."""

import json

import pytest
from starlette.testclient import TestClient

from app.api.events import InMemoryEventBus
from app.api.server import create_app
from app.providers.contracts import ProviderBundle
from app.providers.mock import (
    MockCatalogProvider,
    MockKnowledgeRetriever,
    MockWebProvider,
)


def _bundle():
    return ProviderBundle(
        web=MockWebProvider(),
        catalog=MockCatalogProvider(),
        knowledge=MockKnowledgeRetriever(),
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
        assert json.loads(ws.receive_text())["type"] == "pong"


def test_ws_subscription_before_accept(client, events):
    tid = "00000000-0000-4000-8000-0000000000d1"
    with client.websocket_connect(f"/ws/{tid}") as ws:
        events.emit(tid, "tool_started", "s", {"tool_name": "t"})
        assert json.loads(ws.receive_text())["type"] == "tool_started"


def test_ws_thread_isolation(client, events):
    tid_a = "00000000-0000-4000-8000-0000000000d4"
    tid_b = "00000000-0000-4000-8000-0000000000d5"
    with client.websocket_connect(f"/ws/{tid_a}") as ws_a:
        with client.websocket_connect(f"/ws/{tid_b}") as ws_b:
            events.emit(tid_a, "tool_started", "a", {"tool_name": "t"})
            events.emit(tid_b, "tool_started", "b", {"tool_name": "t"})
            assert json.loads(ws_a.receive_text())["message"] == "a"
            assert json.loads(ws_b.receive_text())["message"] == "b"


def test_ws_overflow_close_1013(events):
    from app.agent.runtime import MockTutorialRuntime
    from app.settings import Phase2Settings

    tid = "00000000-0000-4000-8000-0000000000d7"
    small_bus = InMemoryEventBus(max_queue_size=2)
    app = create_app(
        settings=Phase2Settings(),
        bundle=_bundle(),
        runtime=MockTutorialRuntime(_bundle(), small_bus),
        events=small_bus,
    )
    tc = TestClient(app)
    with tc.websocket_connect(f"/ws/{tid}") as ws:
        # Overflow the small queue
        for i in range(10):
            small_bus.emit(tid, "tool_started", f"m{i}", {"tool_name": "t"})
        # Should eventually close with 1013
        try:
            while True:
                ws.receive_text()
        except Exception as exc:
            code = getattr(exc, "code", getattr(exc, "close_code", None))
            assert code == 1013, f"Expected 1013, got {code}"


def test_ws_overflow_1013_other_thread_and_future_subscription_usable():
    from app.agent.runtime import MockTutorialRuntime
    from app.settings import Phase2Settings

    tid_a = "00000000-0000-4000-8000-0000000000e1"
    tid_b = "00000000-0000-4000-8000-0000000000e2"
    small_bus = InMemoryEventBus(max_queue_size=2)
    app = create_app(
        settings=Phase2Settings(),
        bundle=_bundle(),
        runtime=MockTutorialRuntime(_bundle(), small_bus),
        events=small_bus,
    )
    tc = TestClient(app)
    with tc.websocket_connect(f"/ws/{tid_a}") as ws_a:
        with tc.websocket_connect(f"/ws/{tid_b}") as ws_b:
            # Overflow only tid_a's subscription.
            for i in range(100):
                small_bus.emit(tid_a, "tool_started", f"a{i}", {"tool_name": "t"})
            # Only ws_a is closed, with code 1013.
            try:
                while True:
                    ws_a.receive_text()
            except Exception as exc:
                code = getattr(exc, "code", getattr(exc, "close_code", None))
                assert code == 1013, f"Expected 1013, got {code}"
            # Other thread's subscriber is untouched: ping works and it
            # receives only its own thread's events.
            ws_b.send_text(json.dumps({"type": "ping"}))
            assert json.loads(ws_b.receive_text())["type"] == "pong"
            small_bus.emit(tid_b, "tool_started", "b1", {"tool_name": "t"})
            assert json.loads(ws_b.receive_text())["message"] == "b1"
    # Future subscription on the overflowed thread remains usable.
    with tc.websocket_connect(f"/ws/{tid_a}") as ws_c:
        small_bus.emit(tid_a, "tool_started", "future", {"tool_name": "t"})
        assert json.loads(ws_c.receive_text())["message"] == "future"


def test_ws_normal_close_cleanup(client, events):
    """Normal close removes the subscription; a fresh one sees no replay."""
    tid = "00000000-0000-4000-8000-0000000000e3"
    with client.websocket_connect(f"/ws/{tid}") as ws:
        events.emit(tid, "tool_started", "first", {"tool_name": "t"})
        assert json.loads(ws.receive_text())["message"] == "first"
    # Events emitted while disconnected reach nobody; a new subscription
    # receives only events emitted after it connected.
    events.emit(tid, "tool_started", "during-gap", {"tool_name": "t"})
    with client.websocket_connect(f"/ws/{tid}") as ws2:
        events.emit(tid, "tool_started", "second", {"tool_name": "t"})
        assert json.loads(ws2.receive_text())["message"] == "second"


@pytest.mark.asyncio
async def test_ws_disconnect_keeps_backend_task_active(events, tmp_path):
    """Disconnect removes only the subscriber; the active task is never
    cancelled and completes normally when released."""
    import asyncio

    from app.agent.runtime import RuntimeResult
    from app.api.tasks import TaskRegistry
    from app.settings import Phase2Settings

    class BlockingRuntime:
        def __init__(self):
            self.entered = asyncio.Event()
            self._gate = asyncio.Event()

        async def run(self, request):
            self.entered.set()
            await self._gate.wait()
            return RuntimeResult(answer="ok", artifacts=())

        def release(self):
            self._gate.set()

    runtime = BlockingRuntime()
    tid = "00000000-0000-4000-8000-0000000000e4"
    app = create_app(
        settings=Phase2Settings(),
        bundle=_bundle(),
        runtime=runtime,
        events=events,
    )
    registry = TaskRegistry(
        runtime=runtime,
        events=events,
        base_upload=str(tmp_path / "updated"),
        base_output=str(tmp_path / "output"),
    )
    tc = TestClient(app)
    with tc.websocket_connect(f"/ws/{tid}") as ws:
        assert registry.start("research", thread_id=tid) == tid
        assert json.loads(ws.receive_text())["type"] == "task_started"
        # Task is provably mid-run and blocked inside the runtime.
        await asyncio.wait_for(runtime.entered.wait(), timeout=2.0)
    # Disconnected: only the subscriber is gone; the backend task is alive.
    assert registry.active_count == 1
    # Releasing the task still completes it — disconnect never cancelled it.
    async with events.subscribe(tid) as sub:
        runtime.release()
        terminal = await asyncio.wait_for(sub.queue.get(), timeout=2.0)
        while not sub.queue.empty():
            sub.queue.get_nowait()
    assert terminal.type == "task_completed"
    assert registry.active_count == 0
