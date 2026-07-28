"""Tests for examples.phase1.events — NormalizedChunk and normalize_chunk."""

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

from examples.phase1.events import NormalizedChunk, normalize_chunk, render_chunk


class TestNormalizeChunk:
    def test_aimessage(self):
        msg = AIMessage(content="Hello world")
        chunks = normalize_chunk(msg)
        assert len(chunks) == 1
        c = chunks[0]
        assert c.event_type == "assistant"
        assert c.text == "Hello world"
        assert c.agent_name is None
        assert c.tool_name is None

    def test_aimessagechunk(self):
        msg = AIMessageChunk(content="partial")
        chunks = normalize_chunk(msg)
        assert len(chunks) >= 1
        c = chunks[0]
        assert c.event_type == "assistant_chunk"
        assert "partial" in c.text

    def test_toolmessage(self):
        msg = ToolMessage(content="tool result", tool_call_id="call_1")
        chunks = normalize_chunk(msg)
        assert len(chunks) == 1
        c = chunks[0]
        assert c.event_type == "tool"
        assert c.text == "tool result"

    def test_dict_event_with_type(self):
        event = {"type": "on_chat_model_stream", "content": "streaming text"}
        chunks = normalize_chunk(event)
        assert len(chunks) >= 1
        # Should handle dict events gracefully

    def test_tuple_event(self):
        event = ("agent", AIMessage(content="from tuple"))
        chunks = normalize_chunk(event)
        assert len(chunks) >= 1

    def test_list_event(self):
        event = [AIMessage(content="from list")]
        chunks = normalize_chunk(event)
        assert len(chunks) >= 1

    def test_none_returns_empty(self):
        chunks = normalize_chunk(None)
        assert chunks == []

    def test_unknown_object(self):
        """Unknown objects must not raise; they produce event_type=unknown."""
        chunks = normalize_chunk(object())
        assert len(chunks) >= 1
        assert any(c.event_type == "unknown" for c in chunks)


class TestNormalizedChunkFields:
    def test_all_fields_present(self):
        c = NormalizedChunk(
            event_type="test",
            agent_name="agent1",
            text="sample",
            tool_name="tool1",
            raw_type="AIMessage",
        )
        assert c.event_type == "test"
        assert c.agent_name == "agent1"
        assert c.text == "sample"
        assert c.tool_name == "tool1"
        assert c.raw_type == "AIMessage"

    def test_optional_fields_none(self):
        c = NormalizedChunk(
            event_type="test",
            agent_name=None,
            text="",
            tool_name=None,
            raw_type="unknown",
        )
        assert c.agent_name is None
        assert c.tool_name is None


class TestRenderChunk:
    def test_render_format(self):
        c = NormalizedChunk(
            event_type="assistant",
            agent_name="main",
            text="Hello",
            tool_name=None,
            raw_type="AIMessage",
        )
        rendered = render_chunk(c)
        assert "assistant" in rendered.lower()
        assert "Hello" in rendered
