"""Integration: failure, cancel and rerun closure over the real WebSocket path.

Every scenario drives the product stack — TaskRegistry, InMemoryEventBus,
MockTutorialRuntime, FastAPI HTTP + WebSocket endpoints — exclusively through
HTTP and /ws/{thread_id}. Events are collected only from the socket until a
terminal event arrives, and each scenario asserts exactly one terminal event
(task_failed / task_cancelled / task_completed), i.e. no duplicate terminals.

Providers are swapped for deterministic doubles:
- FailingWebProvider raises inside the product runtime's to_thread call;
- SlowWebProvider blocks briefly so a user cancel lands mid-run;
- FlakyWebProvider fails once, then succeeds (rerun evidence).

The TestClient is entered with ``with TestClient(...) as client`` so one
portal/event loop stays alive for the whole scenario (same pattern as the e2e
closure tests): the background task lifecycle must survive past the POST
response. Without the shared portal, TestClient mints a fresh loop per request
and the run is cancelled when that request's loop shuts down.
"""

import time
import uuid

from starlette.testclient import TestClient

from app.agent.runtime import MockTutorialRuntime
from app.api.events import InMemoryEventBus, TutorialEvent
from app.api.server import create_app
from app.providers.contracts import ProviderBundle
from app.providers.mock import (
    MockCatalogProvider,
    MockKnowledgeProvider,
    MockWebProvider,
)
from app.settings import Phase2Settings

TERMINAL_TYPES = ("task_completed", "task_cancelled", "task_failed")


class RecordingEventBus(InMemoryEventBus):
    """InMemoryEventBus that records every emit through the public API.

    Lets the test prove exactly one terminal event per run from the *whole*
    lifecycle — including anything emitted after the WebSocket delivered its
    first terminal — without reaching into EventBus private state.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._recorded: list[TutorialEvent] = []

    def emit(self, thread_id, event_type, message, data=None):
        event = super().emit(thread_id, event_type, message, data)
        self._recorded.append(event)
        return event

    def events_for(self, thread_id: str) -> list[TutorialEvent]:
        return [e for e in self._recorded if e.thread_id == thread_id]


class FailingWebProvider(MockWebProvider):
    """search() raises a deterministic provider failure."""

    def search(self, query, *, max_results=5):
        raise RuntimeError("web provider exploded: secret-internal-token")


class SlowWebProvider(MockWebProvider):
    """search() blocks its worker thread so cancel lands mid-provider-call."""

    def search(self, query, *, max_results=5):
        time.sleep(0.5)
        return super().search(query, max_results=max_results)


class FlakyWebProvider(MockWebProvider):
    """Fails until ``fail`` is cleared; then behaves like the mock."""

    def __init__(self):
        self.fail = True
        super().__init__()

    def search(self, query, *, max_results=5):
        if self.fail:
            raise RuntimeError("transient provider outage")
        return super().search(query, max_results=max_results)


def _client(web_provider) -> tuple[TestClient, RecordingEventBus]:
    bundle = ProviderBundle(
        web=web_provider,
        catalog=MockCatalogProvider(),
        knowledge=MockKnowledgeProvider(),
        web_mode="mock",
        catalog_mode="mock",
        knowledge_mode="mock",
    )
    events = RecordingEventBus()
    app = create_app(
        settings=Phase2Settings(),
        bundle=bundle,
        runtime=MockTutorialRuntime(bundle, events),
        events=events,
    )
    return TestClient(app), events


def _collect_until_terminal(ws):
    """Read socket events until the first terminal event; return all seen."""
    collected: list[dict] = []
    while True:
        evt = ws.receive_json()
        collected.append(evt)
        if evt["type"] in TERMINAL_TYPES:
            return collected


def _terminal_types(collected) -> list[str]:
    """Terminal types from socket dicts or recorded TutorialEvents."""
    return [
        e["type"] if isinstance(e, dict) else e.type
        for e in collected
        if (e["type"] if isinstance(e, dict) else e.type) in TERMINAL_TYPES
    ]


def _wait_until_stable(
    events: RecordingEventBus,
    thread_id: str,
    quiet_for: float = 0.4,
    timeout: float = 5.0,
) -> None:
    """Block until no new events arrive for ``quiet_for`` seconds.

    The socket stops at the first terminal; a buggy run could still emit a
    duplicate terminal afterwards (the very defect this suite guards). We let
    the recorded stream go quiet so the whole-run assertions below cover it.
    """
    last_count = len(events.events_for(thread_id))
    last_change = time.monotonic()
    deadline = time.monotonic() + timeout
    while True:
        time.sleep(0.05)
        count = len(events.events_for(thread_id))
        if count != last_count:
            last_count = count
            last_change = time.monotonic()
        elif time.monotonic() - last_change >= quiet_for:
            return
        if time.monotonic() >= deadline:
            raise AssertionError(
                f"event stream for {thread_id} did not stabilise within {timeout}s"
            )


def test_provider_failure_emits_single_task_failed_via_websocket():
    tid = str(uuid.uuid4())

    client, events = _client(FailingWebProvider())
    with client:
        with client.websocket_connect(f"/ws/{tid}") as ws:
            r = client.post(
                "/api/task", json={"query": "research aspirin", "thread_id": tid}
            )
            assert r.status_code == 202, r.text
            collected = _collect_until_terminal(ws)
        _wait_until_stable(events, tid)
        recorded = events.events_for(tid)

    # Exactly one terminal event, and it is task_failed — never a duplicate
    # or a fake completion after the provider blew up.
    assert _terminal_types(collected) == ["task_failed"]
    # Whole-run recording (everything after the first terminal included):
    # the lifecycle is stable and still emitted exactly one terminal.
    assert _terminal_types(recorded) == ["task_failed"]
    failed = collected[-1]
    # Terminal event is redacted: no exception text, no internal details.
    assert failed["message"] == ""
    assert failed["data"] == {}
    assert "secret-internal-token" not in failed["message"]


def test_user_cancel_emits_single_task_cancelled_via_websocket():
    tid = str(uuid.uuid4())

    client, events = _client(SlowWebProvider())
    with client:
        with client.websocket_connect(f"/ws/{tid}") as ws:
            r = client.post(
                "/api/task", json={"query": "research aspirin", "thread_id": tid}
            )
            assert r.status_code == 202, r.text
            time.sleep(0.15)  # let the run enter the slow provider call
            r = client.post(f"/api/task/{tid}/cancel")
            assert r.status_code == 200, r.text
            assert r.json()["status"] in ("cancelled", "cancelling")
            collected = _collect_until_terminal(ws)
        _wait_until_stable(events, tid)
        recorded = events.events_for(tid)

    # Exactly one terminal event, and it is task_cancelled.
    assert _terminal_types(collected) == ["task_cancelled"]
    assert _terminal_types(recorded) == ["task_cancelled"]


def test_duplicate_cancel_no_second_terminal_and_explainable_status():
    tid = str(uuid.uuid4())

    client, events = _client(SlowWebProvider())
    with client:
        with client.websocket_connect(f"/ws/{tid}") as ws:
            r = client.post(
                "/api/task", json={"query": "research aspirin", "thread_id": tid}
            )
            assert r.status_code == 202, r.text
            time.sleep(0.15)  # let the run enter the slow provider call

            r1 = client.post(f"/api/task/{tid}/cancel")
            r2 = client.post(f"/api/task/{tid}/cancel")

            # Both responses must be explainable: 200 with a known cancel
            # status, or 404 when terminal cleanup already removed the task.
            for response in (r1, r2):
                if response.status_code == 200:
                    assert response.json()["status"] in ("cancelled", "cancelling")
                else:
                    assert response.status_code == 404, response.text

            collected = _collect_until_terminal(ws)
        _wait_until_stable(events, tid)
        recorded = events.events_for(tid)

    # The duplicate cancel must not fabricate a second terminal event.
    assert _terminal_types(collected) == ["task_cancelled"]
    assert _terminal_types(recorded) == ["task_cancelled"]


def test_rerun_same_thread_after_failure_succeeds():
    provider = FlakyWebProvider()
    tid = str(uuid.uuid4())

    client, events = _client(provider)
    with client:
        # First run fails inside the provider.
        with client.websocket_connect(f"/ws/{tid}") as ws:
            first_start = len(events.events_for(tid))
            r = client.post("/api/task", json={"query": "first run", "thread_id": tid})
            assert r.status_code == 202, r.text
            collected = _collect_until_terminal(ws)
        assert _terminal_types(collected) == ["task_failed"]
        _wait_until_stable(events, tid)
        first_run = events.events_for(tid)[first_start:]

        # The same thread can start a brand-new run (as the React workbench
        # does after a failure): fresh socket, new task, normal completion.
        provider.fail = False
        with client.websocket_connect(f"/ws/{tid}") as ws:
            second_start = len(events.events_for(tid))
            r = client.post("/api/task", json={"query": "second run", "thread_id": tid})
            assert r.status_code == 202, r.text
            collected = _collect_until_terminal(ws)
        assert _terminal_types(collected) == ["task_completed"]
        _wait_until_stable(events, tid)
        second_run = events.events_for(tid)[second_start:]

    # Each run emits exactly one terminal: failure for run 1, completion for
    # run 2 — no duplicate terminals from either lifecycle.
    assert _terminal_types(first_run) == ["task_failed"]
    assert _terminal_types(second_run) == ["task_completed"]
