"""In-memory TaskRegistry — sole owner of task lifecycle events.

Phase 2 stores tasks and events in memory only.
"""

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

    Owns task_started and exactly one of task_completed/task_cancelled/
    task_failed. No persistence, replay, or recovery in Phase 2.
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
        """Start a task. Returns thread_id.

        Uses provided thread_id or generates a UUID. Atomically rejects
        if an active task already exists for the given thread_id.
        task_started is emitted synchronously before the asyncio task.
        """
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

        # task_started emitted synchronously before create_task
        self._events.emit(tid, "task_started", query, {})

        request = RuntimeRequest(query=query, context=ctx)
        task = asyncio.create_task(self._run_lifecycle(request, tid))
        self._tasks[tid] = task
        return tid

    def get(self, thread_id: str) -> asyncio.Task[object] | None:
        return self._tasks.get(thread_id)

    async def cancel(self, thread_id: str) -> str:
        """Cancel a running task."""
        task = self._tasks.get(thread_id)
        if task is None or task.done():
            return "not_found"
        was_cancelled = task.cancel()
        if was_cancelled:
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except Exception:
                pass
            return "cancelled"
        return "cancelling"

    async def _run_lifecycle(self, request: RuntimeRequest, thread_id: str) -> None:
        """Run the runtime and emit exactly one terminal event."""
        try:
            result = await self._runtime.run(request)
            self._events.emit(
                thread_id,
                "task_completed",
                result.answer[:200],
                {"artifacts": list(result.artifacts)},
            )
        except asyncio.CancelledError:
            self._events.emit(thread_id, "task_cancelled", "cancelled", {})
        except Exception:
            self._events.emit(
                thread_id,
                "task_failed",
                "task execution failed",
                {},
            )
        finally:
            self._tasks.pop(thread_id, None)

    @property
    def active_count(self) -> int:
        return sum(1 for t in self._tasks.values() if not t.done())
