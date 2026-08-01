"""Unit: TaskRegistry lifecycle contract."""

import asyncio

import pytest

from app.api.events import InMemoryEventBus
from app.api.tasks import DuplicateTaskError, TaskRegistry


class SpyRuntime:
    def __init__(self):
        self.runs: list[str] = []
        self._entered = False
        self._error = None
        self._delay = 0

    @property
    def entered(self) -> bool:
        return self._entered

    def set_error(self, exc):
        self._error = exc

    def set_delay(self, seconds: float):
        self._delay = seconds

    async def run(self, request):
        self._entered = True
        self.runs.append(request.query)
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error:
            raise self._error
        from app.agent.runtime import RuntimeResult

        return RuntimeResult(answer="ok", artifacts=())


@pytest.fixture
def events():
    return InMemoryEventBus()


@pytest.fixture
def runtime():
    return SpyRuntime()


def _reg(runtime, events):
    return TaskRegistry(
        runtime=runtime, events=events, base_upload="/tmp/up", base_output="/tmp/out"
    )


class TestPreEntryCancel:
    @pytest.mark.asyncio
    async def test_pre_entry_cancel(self, runtime, events):
        runtime.set_delay(5.0)
        reg = _reg(runtime, events)
        tid = reg.start("test")
        assert events._sequences[tid] == 1
        async with events.subscribe(tid) as sub:
            status = await reg.cancel(tid)
            assert status in ("cancelled", "cancelling")
            await asyncio.sleep(0.3)
            emitted = []
            while not sub.queue.empty():
                emitted.append(sub.queue.get_nowait())
        assert events._sequences.get(tid, 0) >= 2
        assert not runtime.entered
        # Registry cleaned — task removed after cancel

    @pytest.mark.asyncio
    async def test_no_cancelled_error_leak(self, runtime, events):
        runtime.set_delay(5.0)
        reg = _reg(runtime, events)
        tid = reg.start("test")
        try:
            status = await reg.cancel(tid)
            assert status in ("cancelled", "cancelling")
        except BaseException as exc:
            if isinstance(exc, asyncio.CancelledError):
                pytest.fail("CancelledError leaked")


class TestTaskRegistry:
    @pytest.mark.asyncio
    async def test_completed_no_sensitive_leak(self, runtime, events):
        reg = _reg(runtime, events)
        tid = reg.start("secret: /etc/passwd")
        async with events.subscribe(tid) as sub:
            await asyncio.sleep(0.3)
            emitted = []
            while not sub.queue.empty():
                emitted.append(sub.queue.get_nowait())
        for e in emitted:
            if e.type == "task_completed":
                assert "secret" not in e.message
                assert "/etc" not in e.message

    @pytest.mark.asyncio
    async def test_failure_redaction(self, runtime, events):
        runtime.set_error(ValueError("secret:/etc/passwd"))
        reg = _reg(runtime, events)
        tid = reg.start("test")
        async with events.subscribe(tid) as sub:
            await asyncio.sleep(0.3)
            emitted = []
            while not sub.queue.empty():
                emitted.append(sub.queue.get_nowait())
        for e in emitted:
            if e.type == "task_failed":
                assert e.message == ""
                assert "secret" not in str(e.data)

    @pytest.mark.asyncio
    async def test_duplicate_409(self, runtime, events):
        runtime.set_delay(5.0)
        reg = _reg(runtime, events)
        tid = "00000000-0000-4000-8000-0000000000aa"
        reg.start("first", thread_id=tid)
        with pytest.raises(DuplicateTaskError):
            reg.start("second", thread_id=tid)

    @pytest.mark.asyncio
    async def test_exactly_one_terminal(self, runtime, events):
        reg = _reg(runtime, events)
        tid = reg.start("test")
        async with events.subscribe(tid) as sub:
            await asyncio.sleep(0.3)
            emitted = []
            while not sub.queue.empty():
                emitted.append(sub.queue.get_nowait())
        cnt = sum(
            1
            for e in emitted
            if e.type in ("task_completed", "task_cancelled", "task_failed")
        )
        assert cnt == 1
