"""In-memory TaskRegistry — sole owner of task lifecycle events."""

import asyncio
import uuid

from app.agent.runtime import RuntimeRequest, TutorialRuntime
from app.api.context import SessionContext
from app.api.events import InMemoryEventBus
from app.tools.files import SessionWorkspace


class DuplicateTaskError(ValueError):
    """A task with this thread_id is already active."""


class TaskRegistry:
    """In-memory task lifecycle manager.

    Owns task_started and exactly one terminal event. Pre-entry
    cancellation emits task_cancelled and cleans registry without
    leaking CancelledError to callers.
    """

    def __init__(
        self,
        runtime: TutorialRuntime,
        events: InMemoryEventBus,
        base_upload: str,
        base_output: str,
    ):
        self._runtime = runtime
        self._events = events
        self._base_upload = base_upload
        self._base_output = base_output
        self._tasks: dict[str, asyncio.Task[object]] = {}

    def start(self, query: str, thread_id: str | None = None) -> str:
        tid = thread_id or str(uuid.uuid4())
        existing = self._tasks.get(tid)
        if existing is not None and not existing.done():
            raise DuplicateTaskError(f"Task {tid} is already running")
        ws = SessionWorkspace.for_thread(
            thread_id=tid,
            base_upload=self._base_upload,
            base_output=self._base_output,
        )
        ctx = SessionContext(thread_id=tid, workspace=ws)
        self._events.emit(tid, "task_started", query, {})
        request = RuntimeRequest(query=query, context=ctx)
        task = asyncio.create_task(self._run_lifecycle(request, tid))
        self._tasks[tid] = task
        return tid

    async def cancel(self, thread_id: str) -> str:
        task = self._tasks.get(thread_id)
        if task is None or task.done():
            return "not_found"
        was_cancelled = task.cancel()
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except BaseException:
            pass
        # If coroutine never ran, emit task_cancelled manually
        if was_cancelled and task.cancelled():
            self._emit_terminal(thread_id, "task_cancelled")
            self._tasks.pop(thread_id, None)
            return "cancelled"
        if task.done():
            return "cancelled"
        return "cancelling"

    def _emit_terminal(self, thread_id: str, etype: str) -> None:
        """Emit a stable, non-sensitive terminal event."""
        self._events.emit(thread_id, etype, "", {})

    async def _run_lifecycle(self, request: RuntimeRequest, thread_id: str) -> None:
        try:
            await self._runtime.run(request)
            self._emit_terminal(thread_id, "task_completed")
        except BaseException as exc:
            if isinstance(exc, asyncio.CancelledError):
                self._emit_terminal(thread_id, "task_cancelled")
            elif isinstance(exc, Exception):
                self._emit_terminal(thread_id, "task_failed")
            else:
                raise
        finally:
            self._tasks.pop(thread_id, None)

    @property
    def active_count(self) -> int:
        return sum(1 for t in self._tasks.values() if not t.done())
