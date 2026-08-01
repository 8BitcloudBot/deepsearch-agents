"""Concrete in-memory event bus with live-only subscriptions.

Phase 2 has exactly one event implementation. No EventSink/EventSource
protocols. No history, replay, or persistence.
"""

import asyncio
import datetime
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _validate_json_value_strict(v: object, path: str = "data") -> None:
    """Strict recursive JSON-only validator. Rejects bytes, set, tuple, etc."""
    if v is None:
        return
    if isinstance(v, bool):
        return
    if isinstance(v, int) and not isinstance(v, bool):
        return
    if isinstance(v, float):
        return
    if isinstance(v, str):
        return
    if isinstance(v, list):
        for i, item in enumerate(v):
            _validate_json_value_strict(item, f"{path}[{i}]")
        return
    if isinstance(v, dict):
        for k, val in v.items():
            if not isinstance(k, str):
                raise ValueError(
                    f"{path}: dict keys must be str, got {type(k).__name__}"
                )
            _validate_json_value_strict(val, f"{path}.{k}")
        return
    raise ValueError(
        f"{path}: value must be JSON-compatible (None/bool/int/float/str/"
        f"list/dict), got {type(v).__name__}"
    )


type JsonValue = (
    None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
)


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
    data: dict[str, JsonValue] = Field(default_factory=dict)
    timestamp: datetime.datetime

    @field_validator("data", mode="before")
    @classmethod
    def _validate_data(cls, value: object) -> object:
        _validate_json_value_strict(value)
        return value


@dataclass(eq=False)
class EventSubscription:
    queue: asyncio.Queue[TutorialEvent]
    overflowed: asyncio.Event


class InMemoryEventBus:
    """Per-thread monotonic event bus with bounded live subscriptions."""

    def __init__(
        self,
        clock: Callable[[], datetime.datetime] | None = None,
        max_queue_size: int = 256,
    ):
        self._clock = clock or (lambda: datetime.datetime.now(datetime.UTC))
        self._max_queue_size = max_queue_size
        self._sequences: dict[str, int] = {}
        self._subscriptions: dict[str, list[EventSubscription]] = {}

    def emit(
        self,
        thread_id: str,
        event_type: TutorialEventType,
        message: str,
        data: dict[str, JsonValue] | None = None,
    ) -> TutorialEvent:
        seq = self._sequences.get(thread_id, 0) + 1
        self._sequences[thread_id] = seq
        event = TutorialEvent(
            sequence=seq,
            thread_id=thread_id,
            type=event_type,
            message=message,
            data={} if data is None else data,
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
        queue: asyncio.Queue[TutorialEvent] = asyncio.Queue(
            maxsize=self._max_queue_size
        )
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
