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
    # ── positive cases ──
    @pytest.mark.parametrize(
        "good",
        [
            None,
            True,
            False,
            0,
            42,
            3.14,
            "hello",
            [],
            [1, "a", None],
            {},
            {"key": "value"},
            {"nested": {"deep": [1, 2, None]}},
        ],
    )
    def test_valid_json_values_accepted(self, good):
        bus = InMemoryEventBus()
        bus.emit("t", "task_started", "m", {"k": good})

    def test_rejects_toplevel_non_dict_values(self):
        """emit(data=non-dict) must be rejected, not silently coerced to {}."""
        from pydantic import ValidationError

        bus = InMemoryEventBus()
        for bad in [b"", set(), tuple(), "", 0, False, []]:
            with pytest.raises(ValidationError):
                bus.emit("t", "task_started", "m", bad)

    def test_none_data_accepted(self):
        """emit(data=None) must be accepted (default {})."""
        bus = InMemoryEventBus()
        bus.emit("t", "task_started", "m", None)

    # ── negative cases ──
    @pytest.mark.parametrize(
        "bad",
        [
            object(),
            b"x",
            bytearray(b"x"),
            {"x"},
            frozenset({"x"}),
            ("x",),
            {1: "bad"},
            {"nested": {"bad": object()}},
            {"nested": [("x",)]},
        ],
    )
    def test_event_data_rejects_non_json_values(self, bad):
        from pydantic import ValidationError

        bus = InMemoryEventBus()
        with pytest.raises(ValidationError):
            bus.emit("t", "task_started", "m", {"bad": bad})


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


class TestSubscriptionCleanup:
    @pytest.mark.asyncio
    async def test_exception_in_subscribe_body_removes_subscription(self):
        bus = InMemoryEventBus()
        with pytest.raises(ValueError):
            async with bus.subscribe("t") as sub:
                assert bus._subscriptions["t"] == [sub]
                raise ValueError("boom")
        assert bus._subscriptions.get("t") == []

    @pytest.mark.asyncio
    async def test_overflow_isolated_across_threads(self):
        bus = InMemoryEventBus(max_queue_size=2)
        async with bus.subscribe("a") as sub_a:
            async with bus.subscribe("b") as sub_b:
                for i in range(5):
                    bus.emit("a", "tool_started", str(i))
                assert sub_a.overflowed.is_set()
                assert not sub_b.overflowed.is_set()
                bus.emit("b", "tool_started", "live")
                ev = await asyncio.wait_for(sub_b.queue.get(), timeout=1)
                assert ev.message == "live"


class TestTypeAnnotations:
    def test_data_field_is_dict_str_jsonvalue_not_any(self):
        """TutorialEvent.data typed as dict[str, JsonValue] via PEP 695 type."""
        from app.api.events import TutorialEvent

        ann = TutorialEvent.model_fields["data"].annotation
        ann_str = str(ann)
        assert "JsonValue" in ann_str, (
            f"data field must reference JsonValue, got {ann_str}"
        )
        assert "Any" not in ann_str, f"data field must not use Any, got {ann_str}"

    def test_object_rejected(self):
        """Non-JSON object() must be rejected at construction."""
        import pytest
        from pydantic import ValidationError

        from app.api.events import TutorialEvent

        with pytest.raises(ValidationError):
            TutorialEvent(
                version=1,
                sequence=1,
                thread_id="t",
                type="task_started",
                message="m",
                data={"bad": object()},
                timestamp=__import__("datetime").datetime.now(),
            )

    def test_json_schema_has_jsonvalue_definition(self):
        """Pydantic must generate a $defs/JsonValue in the JSON Schema."""
        from app.api.events import TutorialEvent

        schema = TutorialEvent.model_json_schema()
        defs = schema.get("$defs", {})
        assert "JsonValue" in defs, (
            f"JSON Schema $defs must contain JsonValue, got keys: {list(defs)}"
        )

    def test_nested_json_data_accepted(self):
        """Deeply nested JSON-compatible data must be accepted."""
        from app.api.events import TutorialEvent

        TutorialEvent(
            version=1,
            sequence=1,
            thread_id="t",
            type="task_started",
            message="m",
            data={
                "key": "value",
                "nested": {"a": [1, 2, {"deep": None}]},
            },
            timestamp=__import__("datetime").datetime.now(),
        )

    def test_schema_data_additional_properties_references_jsonvalue(self):
        """JSON Schema data.additionalProperties must reference JsonValue."""
        from app.api.events import TutorialEvent

        schema = TutorialEvent.model_json_schema()
        data_prop = schema["properties"]["data"]
        ap = data_prop.get("additionalProperties", {})
        ref = ap.get("$ref", "")
        assert "JsonValue" in ref, (
            f"data.additionalProperties must reference JsonValue, got {ref}"
        )
