"""Tests for the concrete InMemoryEventBus and TutorialEvent."""

import asyncio
import datetime

import pytest

from app.api.events import InMemoryEventBus, TutorialEvent

FIXED_TIME = datetime.datetime(2026, 7, 29, 0, 0, 0, tzinfo=datetime.UTC)


def _mock_clock():
    return FIXED_TIME


def test_emit_returns_typed_event():
    bus = InMemoryEventBus(clock=_mock_clock)
    event = bus.emit("t", "task_started", "start")
    assert isinstance(event, TutorialEvent)
    assert event.version == 1
    assert event.type == "task_started"
    assert event.thread_id == "t"
    assert event.message == "start"
    assert event.timestamp == FIXED_TIME


def test_sequences_are_isolated_by_thread():
    bus = InMemoryEventBus(clock=_mock_clock)
    assert bus.emit("a", "task_started", "s").sequence == 1
    assert bus.emit("b", "task_started", "s").sequence == 1
    assert bus.emit("a", "tool_started", "w").sequence == 2


def test_event_serialization_shape():
    bus = InMemoryEventBus(clock=_mock_clock)
    event = bus.emit("t", "tool_started", "searching", {"tool_name": "web"})
    d = event.model_dump()
    assert d["version"] == 1
    assert d["thread_id"] == "t"
    assert d["type"] == "tool_started"
    assert d["data"]["tool_name"] == "web"


@pytest.mark.asyncio
async def test_two_subscribers_receive_same_event():
    bus = InMemoryEventBus(clock=_mock_clock)
    async with bus.subscribe("t") as sub_a:
        async with bus.subscribe("t") as sub_b:
            bus.emit("t", "task_started", "start")
            a_ev = await asyncio.wait_for(sub_a.queue.get(), timeout=1)
            b_ev = await asyncio.wait_for(sub_b.queue.get(), timeout=1)
            assert a_ev.type == "task_started"
            assert b_ev.type == "task_started"


@pytest.mark.asyncio
async def test_unsubscribe_is_isolated():
    bus = InMemoryEventBus(clock=_mock_clock)
    async with bus.subscribe("t") as sub_a:
        bus.emit("t", "task_started", "1")
        await asyncio.wait_for(sub_a.queue.get(), timeout=1)
    # sub_a exits scope
    async with bus.subscribe("t") as sub_b:
        bus.emit("t", "tool_started", "2")
        ev = await asyncio.wait_for(sub_b.queue.get(), timeout=1)
        assert ev.type == "tool_started"
        assert ev.sequence == 2  # per-thread counter continues


@pytest.mark.asyncio
async def test_new_subscription_does_not_replay():
    bus = InMemoryEventBus(clock=_mock_clock)
    bus.emit("t", "task_started", "old")
    async with bus.subscribe("t") as sub:
        bus.emit("t", "tool_started", "new")
        ev = await asyncio.wait_for(sub.queue.get(), timeout=1)
        assert ev.message == "new"


@pytest.mark.asyncio
async def test_no_public_history_accessor():
    bus = InMemoryEventBus(clock=_mock_clock)
    assert not hasattr(bus, "history")
    assert not hasattr(bus, "events")
    assert not hasattr(bus, "for_thread")


class TestJsonValueValidation:
    @pytest.mark.parametrize("bad", [object(), b"x", {"x"}, ("x",), {1: "bad"}])
    def test_event_data_rejects_non_json_values(self, bad):
        bus = InMemoryEventBus()
        with pytest.raises((TypeError, ValueError)):
            bus.emit("t", "task_started", "m", {"bad": bad})

    def test_valid_json_values_accepted(self):
        bus = InMemoryEventBus()
        bus.emit("t", "task_started", "m", None)
        bus.emit("t", "task_started", "m", {"k": True, "n": 42, "s": "hi", "l": [1, 2]})


class TestRealOverflowIsolation:
    @pytest.mark.asyncio
    async def test_257_events_overflow_one_subscriber(self):
        bus = InMemoryEventBus()
        async with bus.subscribe("t") as sub_a:
            async with bus.subscribe("t") as sub_b:
                # Drain sub_a first so only sub_b fills up
                for i in range(257):
                    bus.emit("t", "tool_started", str(i))
                    # Drain sub_a as we go
                    while not sub_a.queue.empty():
                        sub_a.queue.get_nowait()
                # sub_a is empty, sub_b should have overflowed
                assert not sub_a.overflowed.is_set()
                assert sub_b.overflowed.is_set()
        # After overflowed sub exits, new subscriber gets only future
        async with bus.subscribe("t") as sub_c:
            bus.emit("t", "tool_started", "future")
            ev = await asyncio.wait_for(sub_c.queue.get(), timeout=1)
            assert ev.message == "future"
