"""Live conversation WebSocket events with bounded queues."""

from __future__ import annotations

import asyncio
import datetime as dt
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "turn.started",
    "stage.changed",
    "answer.delta",
    "evidence.ready",
    "report.updated",
    "turn.completed",
    "turn.failed",
    "turn.cancelled",
]


class ConversationEvent(BaseModel):
    schema_version: Literal["5.0.0"] = "5.0.0"
    sequence: int = Field(ge=1)
    conversation_id: str
    turn_id: str
    type: EventType
    stage: str | None = None
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: dt.datetime


@dataclass
class EventSubscription:
    queue: asyncio.Queue[ConversationEvent]
    overflowed: asyncio.Event


class ConversationEventBus:
    def __init__(self, max_queue_size: int = 128):
        self._max_queue_size = max_queue_size
        self._sequences: dict[str, int] = {}
        self._subscriptions: dict[str, list[EventSubscription]] = {}

    def emit(
        self,
        conversation_id: str,
        turn_id: str,
        event_type: EventType,
        message: str,
        *,
        stage: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> ConversationEvent:
        sequence = self._sequences.get(conversation_id, 0) + 1
        self._sequences[conversation_id] = sequence
        event = ConversationEvent(
            sequence=sequence,
            conversation_id=conversation_id,
            turn_id=turn_id,
            type=event_type,
            stage=stage,
            message=message,
            data=data or {},
            timestamp=dt.datetime.now(dt.UTC),
        )
        subscriptions = self._subscriptions.get(conversation_id, [])
        for subscription in tuple(subscriptions):
            try:
                subscription.queue.put_nowait(event)
            except asyncio.QueueFull:
                subscriptions.remove(subscription)
                subscription.overflowed.set()
        return event

    @asynccontextmanager
    async def subscribe(self, conversation_id: str) -> AsyncIterator[EventSubscription]:
        subscription = EventSubscription(
            queue=asyncio.Queue(maxsize=self._max_queue_size),
            overflowed=asyncio.Event(),
        )
        self._subscriptions.setdefault(conversation_id, []).append(subscription)
        try:
            yield subscription
        finally:
            subscriptions = self._subscriptions.get(conversation_id, [])
            if subscription in subscriptions:
                subscriptions.remove(subscription)
