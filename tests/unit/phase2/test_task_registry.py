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


class BlockingRuntime:
    """Runtime that deterministically blocks until released or cancelled."""

    def __init__(self):
        self.entered = asyncio.Event()
        self._gate = asyncio.Event()

    async def run(self, request):
        self.entered.set()
        await self._gate.wait()
        from app.agent.runtime import RuntimeResult

        return RuntimeResult(answer="ok", artifacts=())

    def release(self):
        self._gate.set()


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


_TERMINALS = ("task_completed", "task_cancelled", "task_failed")


async def _collect_until_terminal(sub, timeout: float = 2.0) -> list:
    """Deterministically drain a subscription until its single terminal event."""
    emitted = []
    while True:
        event = await asyncio.wait_for(sub.queue.get(), timeout=timeout)
        emitted.append(event)
        if event.type in _TERMINALS:
            break
    while not sub.queue.empty():
        emitted.append(sub.queue.get_nowait())
    return emitted


class TestPreEntryCancel:
    @pytest.mark.asyncio
    async def test_pre_entry_cancel_exactly_one_terminal(self, runtime, events):
        runtime.set_delay(5.0)
        reg = _reg(runtime, events)
        tid = "00000000-0000-4000-8000-0000000000bb"
        async with events.subscribe(tid) as sub:
            assert reg.start("test", thread_id=tid) == tid
            status = await reg.cancel(tid)
            assert status == "cancelled"
            assert not runtime.entered
            assert reg.active_count == 0
            emitted = []
            while not sub.queue.empty():
                emitted.append(sub.queue.get_nowait())
        assert [e.type for e in emitted] == ["task_started", "task_cancelled"]
        terminals = [
            e
            for e in emitted
            if e.type in ("task_completed", "task_cancelled", "task_failed")
        ]
        assert len(terminals) == 1
        assert all(e.message == "" and e.data == {} for e in terminals)

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
        # Cancel the pending task so teardown sees no dangling coroutine.
        assert await reg.cancel(tid) in ("cancelled", "cancelling")
        assert reg.active_count == 0

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


class TestTerminalOwnership:
    @pytest.mark.asyncio
    async def test_active_cancel_exactly_one_terminal(self, events):
        runtime = BlockingRuntime()
        reg = _reg(runtime, events)
        tid = "00000000-0000-4000-8000-0000000000cc"
        async with events.subscribe(tid) as sub:
            assert reg.start("test", thread_id=tid) == tid
            await runtime.entered.wait()
            assert await reg.cancel(tid) == "cancelled"
            emitted = []
            while not sub.queue.empty():
                emitted.append(sub.queue.get_nowait())
        assert [e.type for e in emitted] == ["task_started", "task_cancelled"]
        assert reg.active_count == 0

    @pytest.mark.asyncio
    async def test_repeated_cancel_cannot_add_second_terminal(self, events):
        runtime = BlockingRuntime()
        reg = _reg(runtime, events)
        tid = "00000000-0000-4000-8000-0000000000dd"
        async with events.subscribe(tid) as sub:
            assert reg.start("test", thread_id=tid) == tid
            await runtime.entered.wait()
            assert await reg.cancel(tid) == "cancelled"
            assert await reg.cancel(tid) == "not_found"
            emitted = []
            while not sub.queue.empty():
                emitted.append(sub.queue.get_nowait())
        assert [e.type for e in emitted] == ["task_started", "task_cancelled"]
        assert reg.active_count == 0

    @pytest.mark.asyncio
    async def test_failure_exactly_one_terminal(self, runtime, events):
        runtime.set_error(ValueError("boom"))
        reg = _reg(runtime, events)
        tid = "00000000-0000-4000-8000-0000000000ee"
        async with events.subscribe(tid) as sub:
            assert reg.start("test", thread_id=tid) == tid
            emitted = await _collect_until_terminal(sub)
        assert [e.type for e in emitted] == ["task_started", "task_failed"]
        assert reg.active_count == 0

    @pytest.mark.asyncio
    async def test_completion_exactly_one_terminal(self, runtime, events):
        reg = _reg(runtime, events)
        tid = "00000000-0000-4000-8000-0000000000ff"
        async with events.subscribe(tid) as sub:
            assert reg.start("test", thread_id=tid) == tid
            emitted = await _collect_until_terminal(sub)
        assert [e.type for e in emitted] == ["task_started", "task_completed"]
        assert reg.active_count == 0
