"""Concrete in-memory event bus with live-only subscriptions.

Phase 2 has exactly one event implementation. No EventSink/EventSource
protocols. No history, replay, or persistence.
"""

import asyncio
import datetime
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

TutorialEventType = Literal[
    "task_started",
    "agent_started",
    "agent_completed",
    "tool_started",
    "tool_completed",
    "artifact_created",
    "task_completed",
    "task_cancelled",
    "task_failed",
]


class TutorialEvent(BaseModel):
    version: Literal[1] = 1
    sequence: int = Field(ge=1)
    thread_id: str
    type: TutorialEventType
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime.datetime


@dataclass(eq=False)
class EventSubscription:
    queue: asyncio.Queue[TutorialEvent]
    overflowed: asyncio.Event


class InMemoryEventBus:
    """Per-thread monotonic event bus with bounded live subscriptions."""

    def __init__(self, clock: Callable[[], datetime.datetime] | None = None):
        self._clock = clock or (lambda: datetime.datetime.now(datetime.UTC))
        self._sequences: dict[str, int] = {}
        self._subscriptions: dict[str, list[EventSubscription]] = {}

    def emit(
        self,
        thread_id: str,
        event_type: TutorialEventType,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> TutorialEvent:
        seq = self._sequences.get(thread_id, 0) + 1
        self._sequences[thread_id] = seq
        event = TutorialEvent(
            sequence=seq,
            thread_id=thread_id,
            type=event_type,
            message=message,
            data=data or {},
            timestamp=self._clock(),
        )
        subs = self._subscriptions.get(thread_id, [])
        overflowed: list[EventSubscription] = []
        for sub in subs:
            try:
                sub.queue.put_nowait(event)
            except asyncio.QueueFull:
                overflowed.append(sub)
        for sub in overflowed:
            subs.remove(sub)
            sub.overflowed.set()
        return event

    @asynccontextmanager
    async def subscribe(self, thread_id: str) -> AsyncIterator[EventSubscription]:
        queue: asyncio.Queue[TutorialEvent] = asyncio.Queue(maxsize=256)
        sub = EventSubscription(queue=queue, overflowed=asyncio.Event())
        if thread_id not in self._subscriptions:
            self._subscriptions[thread_id] = []
        self._subscriptions[thread_id].append(sub)
        try:
            yield sub
        finally:
            subs = self._subscriptions.get(thread_id, [])
            if sub in subs:
                subs.remove(sub)
