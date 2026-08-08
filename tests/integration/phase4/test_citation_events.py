"""Integration: citation WebSocket events on agent-research tasks (P4-5).

``citation_started`` / ``citation_completed`` are additive, NON-terminal
events. They preserve event ``version: 1`` and the existing event types, and
they never affect the task lifecycle: exactly one terminal event per task,
even when the citation evaluation itself fails (the failure becomes a
redacted limitation on ``citation_completed``, never a ``task_failed``).
"""

import asyncio
import json

import pytest

from app.agent.runtime import RuntimeRequest
from app.api.context import SessionContext
from app.api.events import InMemoryEventBus
from app.research.runtime import AgentResearchRuntime
from app.tools.files import SessionWorkspace

TID = "00000000-0000-4000-8000-000000000501"
TERMINAL_TYPES = {"task_completed", "task_cancelled", "task_failed"}
CITATION_TYPES = {"citation_started", "citation_completed"}

FAKE_SECRET = "sk-test-1234567890abcdef"  # pragma: allowlist secret
POSIX_ABS = "/Users/wxhu/Documents/private/credentials.pem"


@pytest.fixture
def events():
    return InMemoryEventBus()


@pytest.fixture
def workspace(tmp_path):
    return SessionWorkspace.for_thread(
        thread_id=TID,
        base_upload=str(tmp_path / "updated"),
        base_output=str(tmp_path / "output"),
    )


async def _run(runtime, events, workspace, query="Compare agent orchestration."):
    ctx = SessionContext(thread_id=TID, workspace=workspace)
    async with events.subscribe(TID) as sub:
        result = await runtime.run(RuntimeRequest(query, ctx))
        emitted = []
        while not sub.queue.empty():
            emitted.append(sub.queue.get_nowait())
    return result, emitted


@pytest.mark.asyncio
async def test_citation_events_ordered_non_terminal_version_1(events, workspace):
    """Citation events are ordered, redacted-safe, non-terminal, version 1."""
    runtime = AgentResearchRuntime(events)
    result, emitted = await _run(runtime, events, workspace)

    types = [e.type for e in emitted]
    assert "citation_started" in types
    assert "citation_completed" in types
    started = next(e for e in emitted if e.type == "citation_started")
    completed = next(e for e in emitted if e.type == "citation_completed")

    # Event version 1 is preserved and the envelope is unchanged.
    assert started.version == 1
    assert completed.version == 1
    assert started.thread_id == TID
    assert completed.thread_id == TID
    assert started.type != completed.type

    # Ordering: citation_started < citation_completed < agent_completed, and
    # the whole stream keeps strictly increasing, unique sequences.
    assert types.index("citation_started") < types.index("citation_completed")
    assert types.index("citation_completed") < types.index("agent_completed")
    seqs = [e.sequence for e in emitted]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs)

    # Non-terminal: the runtime itself never emits a terminal event, and the
    # citation events are never mistaken for terminal ones.
    assert not (set(types) & TERMINAL_TYPES)

    # Completed payload: deterministic, non-sensitive summary.
    data = completed.data
    assert data["status"] == "completed"
    assert data["partition_count"] == 3
    assert len(data["report_fingerprint"]) == 64
    assert isinstance(data["limitations"], list)
    assert all(isinstance(lim, str) for lim in data["limitations"])

    # The same events carry no absolute paths or secret markers.
    blob = json.dumps([e.model_dump(mode="json") for e in emitted])
    assert POSIX_ABS not in blob
    assert FAKE_SECRET not in blob
    assert "/output/" not in blob


@pytest.mark.asyncio
async def test_citation_failure_becomes_redacted_limitation(
    events, workspace, monkeypatch
):
    """A failing citation evaluation is surfaced as a redacted limitation on
    citation_completed and never emits a terminal event."""

    def boom(*args, **kwargs):
        raise RuntimeError(f"boom with {FAKE_SECRET} at {POSIX_ABS}")

    monkeypatch.setattr("app.research.runtime.load_fixture", boom)
    runtime = AgentResearchRuntime(events)
    result, emitted = await _run(runtime, events, workspace)

    assert result is not None
    completed = next(e for e in emitted if e.type == "citation_completed")
    assert completed.data["status"] == "failed"
    assert completed.data["partition_count"] == 0
    assert completed.data["limitations"]

    blob = json.dumps(completed.data)
    assert FAKE_SECRET not in blob
    assert POSIX_ABS not in blob
    assert not ({e.type for e in emitted} & TERMINAL_TYPES)


@pytest.mark.asyncio
async def test_exactly_one_terminal_event_when_citations_fail(
    events, tmp_path, monkeypatch
):
    """TaskRegistry still owns exactly one terminal event when the citation
    evaluation fails; the failure never creates an extra terminal event."""
    from app.api.tasks import TaskRegistry

    def boom(*args, **kwargs):
        raise RuntimeError("citation engine down")

    monkeypatch.setattr("app.research.runtime.load_fixture", boom)
    runtime = AgentResearchRuntime(events)
    registry = TaskRegistry(
        runtime=runtime,
        events=events,
        base_upload=str(tmp_path / "updated"),
        base_output=str(tmp_path / "output"),
    )

    async with events.subscribe(TID) as sub:
        registry.start("research", thread_id=TID)
        emitted = []
        while True:
            event = await asyncio.wait_for(sub.queue.get(), timeout=10.0)
            emitted.append(event)
            if event.type in TERMINAL_TYPES:
                break

    terminals = [e for e in emitted if e.type in TERMINAL_TYPES]
    assert len(terminals) == 1
    assert terminals[0].type == "task_completed"

    citation = [e for e in emitted if e.type == "citation_completed"]
    assert len(citation) == 1
    assert citation[0].data["status"] == "failed"
    assert registry.active_count == 0
