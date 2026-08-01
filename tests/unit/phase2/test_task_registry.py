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
        self._entered = False

    def set_result(self, result):
        from app.agent.runtime import RuntimeResult

        self._result = result or RuntimeResult(answer="ok", artifacts=())

    def set_error(self, exc):
        self._error = exc

    def set_delay(self, seconds: float):
        self._delay = seconds

    @property
    def entered(self) -> bool:
        return self._entered

    async def run(self, request):
        self._entered = True
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


def _reg(runtime, events):
    return TaskRegistry(
        runtime=runtime,
        events=events,
        base_upload="/tmp/up",
        base_output="/tmp/out",
    )


class TestTaskRegistry:
    @pytest.mark.asyncio
    async def test_task_started_before_create_task(self, runtime, events):
        """task_started emitted synchronously, before async task runs."""
        reg = _reg(runtime, events)
        tid = reg.start("test")
        seq = events._sequences.get(tid, 0)
        assert seq == 1, f"task_started not emitted synchronously (seq={seq})"

    @pytest.mark.asyncio
    async def test_duplicate_active_409(self, runtime, events):
        runtime.set_delay(5.0)
        reg = _reg(runtime, events)
        tid = "00000000-0000-4000-8000-0000000000aa"
        reg.start("first", thread_id=tid)
        with pytest.raises(DuplicateTaskError):
            reg.start("second", thread_id=tid)

    @pytest.mark.asyncio
    async def test_cancel_before_runtime_entry(self, runtime, events):
        """Cancel before runtime.run enters the sleep."""
        runtime.set_delay(10.0)
        reg = _reg(runtime, events)
        tid = reg.start("test")
        # Subscribe before cancel
        async with events.subscribe(tid) as sub:
            # Small delay to let task reach asyncio.sleep
            await asyncio.sleep(0.05)
            status = await reg.cancel(tid)
            assert status == "cancelled"
            await asyncio.sleep(0.3)
            emitted = []
            while not sub.queue.empty():
                emitted.append(sub.queue.get_nowait())
        terminals = {"task_completed", "task_cancelled", "task_failed"}
        terminal_events = [e for e in emitted if e.type in terminals]
        assert len(terminal_events) == 1

    @pytest.mark.asyncio
    async def test_failure_redaction_subscribe_first(self, runtime, events):
        runtime.set_error(ValueError("secret: /etc/passwd P@ssword"))
        reg = _reg(runtime, events)
        tid = reg.start("test")
        async with events.subscribe(tid) as sub:
            await asyncio.sleep(0.3)
            emitted = []
            while not sub.queue.empty():
                emitted.append(sub.queue.get_nowait())
        for e in emitted:
            if e.type == "task_failed":
                assert "/etc/passwd" not in e.message
                assert "secret" not in e.message
                assert "P@ssword" not in e.message
                assert e.message == "task execution failed"

    @pytest.mark.asyncio
    async def test_exactly_one_terminal_per_task(self, runtime, events):
        reg = _reg(runtime, events)
        tid = reg.start("test")
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
        assert len(terminal_events) == 1

    @pytest.mark.asyncio
    async def test_start_accepts_thread_id(self, runtime, events):
        reg = _reg(runtime, events)
        tid = reg.start("test", thread_id="00000000-0000-4000-8000-0000000000bb")
        assert tid == "00000000-0000-4000-8000-0000000000bb"
        await asyncio.sleep(0.3)

    @pytest.mark.asyncio
    async def test_cancel_not_found(self, runtime, events):
        reg = _reg(runtime, events)
        assert await reg.cancel("nonexistent") == "not_found"
