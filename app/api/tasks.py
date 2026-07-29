"""In-memory TaskRegistry — sole owner of task lifecycle events.

Phase 2 stores tasks and events in memory only.
"""

import asyncio
import uuid

from app.agent.runtime import RuntimeRequest, TutorialRuntime
from app.api.context import SessionContext
from app.api.events import InMemoryEventBus
from app.tools.files import SessionWorkspace


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

    def start(self, query: str) -> str:
        """Create and start a task. Returns thread_id.

        Raises ValueError if a task with the same thread_id is active.
        """
        thread_id = str(uuid.uuid4())

        if thread_id in self._tasks and not self._tasks[thread_id].done():
            raise ValueError(f"Task {thread_id} already running")

        ws = SessionWorkspace.for_thread(
            thread_id=thread_id,
            base_upload=self._base_upload,
            base_output=self._base_output,
        )
        ctx = SessionContext(thread_id=thread_id, workspace=ws)

        self._events.emit(thread_id, "task_started", query, {})

        request = RuntimeRequest(query=query, context=ctx)
        task = asyncio.create_task(self._run_lifecycle(request, thread_id))
        self._tasks[thread_id] = task
        return thread_id

    async def cancel(self, thread_id: str) -> str:
        """Cancel a running task. Returns 'cancelled', 'cancelling', or 'not_found'."""
        task = self._tasks.get(thread_id)
        if task is None or task.done():
            return "not_found"
        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=1.0)
            return "cancelled"
        except TimeoutError:
            return "cancelling"

    async def _run_lifecycle(self, request: RuntimeRequest, thread_id: str) -> None:
        """Run the runtime and translate result into terminal events."""
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
            # Remove from registry after terminal event
            self._tasks.pop(thread_id, None)

    @property
    def active_count(self) -> int:
        return sum(1 for t in self._tasks.values() if not t.done())
