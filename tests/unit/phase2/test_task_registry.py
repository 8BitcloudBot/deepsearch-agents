"""Unit: TaskRegistry lifecycle contract."""

import asyncio

import pytest

from app.api.events import InMemoryEventBus
from app.api.tasks import DuplicateTaskError, TaskRegistry


class SpyRuntime:
    def __init__(self):
        self.runs: list[str] = []
        self._result = None
        self._error = None
        self._delay = 0

    def set_result(self, result):
        from app.agent.runtime import RuntimeResult

        self._result = result or RuntimeResult(answer="ok", artifacts=())

    def set_error(self, exc):
        self._error = exc

    def set_delay(self, seconds: float):
        self._delay = seconds

    async def run(self, request):
        self.runs.append(request.query)
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error:
            raise self._error
        return self._result


@pytest.fixture
def events():
    return InMemoryEventBus()


@pytest.fixture
def runtime():
    from app.agent.runtime import RuntimeResult

    rt = SpyRuntime()
    rt.set_result(RuntimeResult(answer="done", artifacts=()))
    return rt


@pytest.fixture
def registry(runtime, events):
    return TaskRegistry(
        runtime=runtime,
        events=events,
        base_upload="/tmp/up",
        base_output="/tmp/out",
    )


class TestTaskRegistry:
    @pytest.mark.asyncio
    async def test_task_started_emitted_synchronously(self, runtime, events):
        """task_started is emitted before the asyncio task runs."""
        registry = TaskRegistry(
            runtime=runtime,
            events=events,
            base_upload="/tmp/up",
            base_output="/tmp/out",
        )
        tid = registry.start("test")
        # task_started must already be in the event stream
        subbed = events._sequences.get(tid, 0)
        assert subbed >= 1, "task_started not emitted synchronously"

    @pytest.mark.asyncio
    async def test_duplicate_active_task_409(self, runtime, events):
        runtime.set_delay(5.0)
        registry = TaskRegistry(
            runtime=runtime,
            events=events,
            base_upload="/tmp/up",
            base_output="/tmp/out",
        )
        tid = "00000000-0000-4000-8000-0000000000aa"
        registry.start("first", thread_id=tid)
        with pytest.raises(DuplicateTaskError):
            registry.start("second", thread_id=tid)

    @pytest.mark.asyncio
    async def test_cancel_before_runtime_entry(self, runtime, events):
        runtime.set_delay(10.0)
        registry = TaskRegistry(
            runtime=runtime,
            events=events,
            base_upload="/tmp/up",
            base_output="/tmp/out",
        )
        tid = registry.start("slow")
        await asyncio.sleep(0.05)
        status = await registry.cancel(tid)
        assert status in ("cancelled", "cancelling")

    @pytest.mark.asyncio
    async def test_active_cancel(self, runtime, events):
        runtime.set_delay(5.0)
        registry = TaskRegistry(
            runtime=runtime,
            events=events,
            base_upload="/tmp/up",
            base_output="/tmp/out",
        )
        tid = registry.start("slow")
        status = await registry.cancel(tid)
        assert status in ("cancelled", "cancelling")

    @pytest.mark.asyncio
    async def test_failure_redaction(self, runtime, events):
        runtime.set_error(ValueError("secret: /etc/passwd P@ssword"))
        registry = TaskRegistry(
            runtime=runtime,
            events=events,
            base_upload="/tmp/up",
            base_output="/tmp/out",
        )
        tid = registry.start("test")
        await asyncio.sleep(0.3)
        async with events.subscribe(tid) as sub:
            emitted = []
            while not sub.queue.empty():
                emitted.append(sub.queue.get_nowait())
        for e in emitted:
            if e.type == "task_failed":
                assert "/etc/passwd" not in e.message
                assert "secret" not in e.message
                assert "P@ssword" not in e.message

    @pytest.mark.asyncio
    async def test_exactly_one_terminal_per_task(self, runtime, events):
        registry = TaskRegistry(
            runtime=runtime,
            events=events,
            base_upload="/tmp/up",
            base_output="/tmp/out",
        )
        tid = registry.start("test")
        async with events.subscribe(tid) as sub:
            await asyncio.sleep(0.3)
            emitted = []
            while not sub.queue.empty():
                emitted.append(sub.queue.get_nowait())
        terminals = {
            "task_completed",
            "task_cancelled",
            "task_failed",
        }
        terminal_events = [e for e in emitted if e.type in terminals]
        assert len(terminal_events) == 1, (
            f"Expected 1 terminal, got {len(terminal_events)}"
        )

    @pytest.mark.asyncio
    async def test_start_accepts_provided_thread_id(self, registry):
        tid = registry.start("test", thread_id="00000000-0000-4000-8000-0000000000bb")
        assert tid == "00000000-0000-4000-8000-0000000000bb"
        await asyncio.sleep(0.3)

    @pytest.mark.asyncio
    async def test_cancel_not_found(self, registry):
        status = await registry.cancel("nonexistent")
        assert status == "not_found"
