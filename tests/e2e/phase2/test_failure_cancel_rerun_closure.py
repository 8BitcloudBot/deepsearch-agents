"""E2E: failure -> single task_failed -> same-thread rerun closure.

Drives the full product closure over the WebSocket path with a toggleable
provider: the first run fails inside the provider (single task_failed on the
socket), then — exactly like the React workbench's second Run click — a fresh
WebSocket is opened for the SAME thread_id, a new task is started, and the run
completes normally with both reports. Events are collected exclusively from
/ws/{thread_id}; no event-bus or registry access.
"""

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

    Proves exactly one terminal event per run from the *whole* lifecycle —
    including anything emitted after the WebSocket delivered its first
    terminal — without reaching into EventBus private state.
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


class FlakyWebProvider(MockWebProvider):
    """Fails the first run, succeeds the rerun."""

    def __init__(self):
        self.fail = True
        super().__init__()

    def search(self, query, *, max_results=5):
        if self.fail:
            raise RuntimeError("upstream search outage")
        return super().search(query, max_results=max_results)


def _terminal_types(events) -> list[str]:
    """Terminal types from socket dicts or recorded TutorialEvents."""
    return [
        e["type"] if isinstance(e, dict) else e.type
        for e in events
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
    duplicate terminal afterwards. We let the recorded stream go quiet so the
    whole-run assertions below cover it.
    """
    import time

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


def _collect_until_terminal(ws) -> list[dict]:
    collected: list[dict] = []
    while True:
        evt = ws.receive_json()
        collected.append(evt)
        if evt["type"] in TERMINAL_TYPES:
            return collected


def test_failure_then_rerun_closure_via_websocket(tmp_path, monkeypatch):
    # Isolate the file root (updated/ and output/ are cwd-relative).
    monkeypatch.chdir(tmp_path)
    tid = str(uuid.uuid4())
    marker = f"UNIQUE-RERUN-MARKER-{uuid.uuid4().hex}"

    provider = FlakyWebProvider()
    bundle = ProviderBundle(
        web=provider,
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

    with TestClient(app) as client:
        # 1. Upload constraints.md carrying a unique marker (read by the
        #    rerun, proving the same workbench session state is reused).
        r = client.post(
            "/api/upload",
            data={"thread_id": tid},
            files={
                "files": (
                    "constraints.md",
                    f"# {marker}\n\nKeep it short.".encode(),
                    "text/markdown",
                )
            },
        )
        assert r.status_code == 200, r.text

        # 2. First run: provider failure -> exactly one task_failed.
        with client.websocket_connect(f"/ws/{tid}") as ws:
            first_start = len(events.events_for(tid))
            r = client.post(
                "/api/task", json={"query": "research aspirin", "thread_id": tid}
            )
            assert r.status_code == 202, r.text
            first_run_socket = _collect_until_terminal(ws)
        terminals = [e["type"] for e in first_run_socket if e["type"] in TERMINAL_TYPES]
        assert terminals == ["task_failed"], terminals
        assert first_run_socket[-1]["message"] == ""  # redacted, no exception text
        _wait_until_stable(events, tid)
        first_run = events.events_for(tid)[first_start:]
        assert _terminal_types(first_run) == ["task_failed"], [
            e.type for e in first_run
        ]

        # 3. Rerun on the same workbench: fresh socket, new task, completion.
        provider.fail = False
        with client.websocket_connect(f"/ws/{tid}") as ws:
            second_start = len(events.events_for(tid))
            r = client.post(
                "/api/task", json={"query": "research aspirin", "thread_id": tid}
            )
            assert r.status_code == 202, r.text
            second_run_socket = _collect_until_terminal(ws)
        terminals = [
            e["type"] for e in second_run_socket if e["type"] in TERMINAL_TYPES
        ]
        assert terminals == ["task_completed"], terminals
        _wait_until_stable(events, tid)
        second_run = events.events_for(tid)[second_start:]
        assert _terminal_types(second_run) == ["task_completed"], [
            e.type for e in second_run
        ]

        # 4. Both reports exist for the same thread and the markdown carries
        #    the uploaded marker — the rerun used the same session.
        r = client.get("/api/files", params={"thread_id": tid})
        assert r.status_code == 200, r.text
        fnames = {f["name"] for f in r.json()["files"]}
        assert "tutorial-report.md" in fnames
        assert "tutorial-report.pdf" in fnames

        r = client.get(
            "/api/download",
            params={"thread_id": tid, "path": "tutorial-report.md"},
        )
        assert r.status_code == 200, r.text
        assert marker in r.text

        # 5. The report PDF is valid.
        r = client.get(
            "/api/download",
            params={"thread_id": tid, "path": "tutorial-report.pdf"},
        )
        assert r.status_code == 200, r.text
        assert r.content[:4] == b"%PDF"
