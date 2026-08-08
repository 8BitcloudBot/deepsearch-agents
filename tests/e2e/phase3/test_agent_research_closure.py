"""E2E: agent-research vertical closure through app.main wiring.

Black-box over the real /ws/{thread_id} WebSocket: uploads a unique
constraint, starts an agent-research task, collects the full event stream
through completion, then drains a bounded post-terminal window so a
duplicate terminal would fail. Lists/downloads the shared
tutorial-report.md/.pdf artifacts and verifies marker, corpus ID and
source modes in the Markdown.
"""

import json
import time

import pytest
from anyio import EndOfStream, WouldBlock
from starlette.testclient import TestClient

UNIQUE_MARKER = "UNIQUE-P3-E2E-CONSTRAINT-20260807"
TID = "00000000-0000-4000-8000-000000000302"
TERMINAL_TYPES = {"task_completed", "task_cancelled", "task_failed"}
DRAIN_WINDOW_S = 0.5


def _poll_event(ws):
    """One buffered event JSON over the live /ws stream, or None.

    The TestClient WebSocket session has no public receive timeout, so the
    bounded drain polls the session's inbound stream with receive_nowait().
    Events are only delivered while a receive() call is in flight, so the
    collection phase uses the public blocking receive_text() (the accepted
    Phase 2 pattern); only the drain needs this non-blocking probe.
    """
    try:
        msg = ws._send_rx.receive_nowait()
    except WouldBlock:
        return None
    except EndOfStream:
        return None
    if msg["type"] != "websocket.send":
        return None
    return json.loads(msg["text"])


def _collect_until_terminal(ws):
    collected = []
    while True:
        evt = json.loads(ws.receive_text())
        collected.append(evt)
        if evt["type"] in TERMINAL_TYPES:
            return collected


def _drain(ws, window_s=DRAIN_WINDOW_S):
    """Bounded post-terminal drain; a second terminal fails the test.

    TestClient delivers bus events only while a receive() call is in
    flight, so each probe sends a ping (a portal call) to flush pending
    events into the stream, then polls the stream non-blockingly.
    """
    drained = []
    deadline = time.monotonic() + window_s
    while time.monotonic() < deadline:
        ws.send_text(json.dumps({"type": "ping"}))
        time.sleep(0.005)
        while True:
            evt = _poll_event(ws)
            if evt is None:
                break
            if evt["type"] == "pong":
                continue
            drained.append(evt)
            if evt["type"] in TERMINAL_TYPES:
                pytest.fail(f"duplicate terminal after completion: {evt['type']}")
    return drained


def test_agent_research_vertical_closure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_PROFILE", "agent-research")

    from app.main import create_app

    app = create_app()
    client = TestClient(app)

    # 1. Upload the unique constraint
    r = client.post(
        "/api/upload",
        data={"thread_id": TID},
        files={
            "files": (
                "constraints.md",
                f"# {UNIQUE_MARKER}\n\nKeep it short.".encode(),
                "text/markdown",
            )
        },
    )
    assert r.status_code == 200

    # 2. Start task and collect events over the real /ws/{thread_id}
    with client.websocket_connect(f"/ws/{TID}") as ws:
        r2 = client.post(
            "/api/task",
            json={
                "query": "Compare single-agent and orchestrator-workers "
                "approaches for agent research.",
                "thread_id": TID,
            },
        )
        assert r2.status_code == 202

        collected = _collect_until_terminal(ws)
        drained = _drain(ws)
        assert drained == []

    # 3. Monotonic per-thread sequence, three tool families, artifacts,
    #    exactly one terminal
    sequences = [e["sequence"] for e in collected]
    assert sequences == sorted(sequences)
    assert len(set(sequences)) == len(sequences)
    assert all(e["thread_id"] == TID for e in collected)
    assert all(e["version"] == 1 for e in collected)

    tool_names = {e["data"].get("tool_name", "") for e in collected}
    assert "read_web_snapshot" in tool_names, f"web: {sorted(tool_names)}"
    assert "read_catalog_entry" in tool_names, f"catalog: {sorted(tool_names)}"
    assert "read_knowledge_notes" in tool_names, f"knowledge: {sorted(tool_names)}"
    for tool in ("read_web_snapshot", "read_catalog_entry", "read_knowledge_notes"):
        started = any(
            e["type"] == "tool_started" and e["data"]["tool_name"] == tool
            for e in collected
        )
        completed = any(
            e["type"] == "tool_completed" and e["data"]["tool_name"] == tool
            for e in collected
        )
        assert started and completed, tool

    artifact_names = {
        e["message"] for e in collected if e["type"] == "artifact_created"
    }
    assert artifact_names == {"tutorial-report.md", "tutorial-report.pdf"}

    terminals = [e for e in collected if e["type"] in TERMINAL_TYPES]
    assert len(terminals) == 1
    assert terminals[0]["type"] == "task_completed"

    # 4. Artifacts list + download
    r = client.get("/api/files", params={"thread_id": TID})
    assert r.status_code == 200
    fnames = {f["name"] for f in r.json()["files"]}
    assert "tutorial-report.md" in fnames
    assert "tutorial-report.pdf" in fnames

    r = client.get(
        "/api/download", params={"thread_id": TID, "path": "tutorial-report.md"}
    )
    assert r.status_code == 200
    md = r.text
    assert len(md) > 50
    assert UNIQUE_MARKER in md
    assert "agent-research" in md
    assert "agent-research-corpus-v1" in md
    assert "## Source Modes" in md

    r = client.get(
        "/api/download", params={"thread_id": TID, "path": "tutorial-report.pdf"}
    )
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_agent_research_one_case_by_id_from_seed10(tmp_path, monkeypatch):
    """P3-2 proof: load one case by ID from seed-10 and run it through the
    same offline agent-research flow; API endpoints are unchanged."""
    from app.evaluation.datasets import load_dataset

    dataset = load_dataset()
    case = next(c for c in dataset.cases if c.case_id == "seed-001")
    assert case.split == "seed"
    assert case.difficulty in {"basic", "intermediate", "advanced"}
    assert case.question

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_PROFILE", "agent-research")

    from app.main import create_app

    app = create_app()
    client = TestClient(app)

    tid = "00000000-0000-4000-8000-000000000303"
    marker = "UNIQUE-P3-2-SEED-001-CASE-MARKER"
    r = client.post(
        "/api/upload",
        data={"thread_id": tid},
        files={
            "files": (
                "constraints.md",
                f"# {marker}\n\nCase: {case.case_id}".encode(),
                "text/markdown",
            )
        },
    )
    assert r.status_code == 200

    with client.websocket_connect(f"/ws/{tid}") as ws:
        r2 = client.post(
            "/api/task",
            json={"query": case.question, "thread_id": tid},
        )
        assert r2.status_code == 202

        collected = _collect_until_terminal(ws)
        drained = _drain(ws)
        assert drained == []

    terminals = [e for e in collected if e["type"] in TERMINAL_TYPES]
    assert len(terminals) == 1
    assert terminals[0]["type"] == "task_completed"

    r = client.get(
        "/api/download", params={"thread_id": tid, "path": "tutorial-report.md"}
    )
    assert r.status_code == 200
    md = r.text
    assert marker in md
    assert case.case_id in md
    assert case.question in md
    assert "agent-research-corpus-v1" in md
