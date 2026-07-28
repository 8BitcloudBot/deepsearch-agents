"""Phase 1 event normalization.

Converts various LangChain/DeepAgents event types into a uniform
NormalizedChunk for display and testing.
"""

from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage


@dataclass(frozen=True)
class NormalizedChunk:
    """Uniform event representation."""

    event_type: str
    agent_name: str | None
    text: str
    tool_name: str | None
    raw_type: str


def normalize_chunk(chunk: object) -> list[NormalizedChunk]:
    """Convert any chunk/event into a list of NormalizedChunk.

    Must handle: AIMessage, AIMessageChunk, ToolMessage, dict, tuple/list,
    None, and unknown objects. Unknown objects produce event_type="unknown"
    and must not raise.
    """
    if chunk is None:
        return []

    if isinstance(chunk, AIMessageChunk):
        return [
            NormalizedChunk(
                event_type="assistant_chunk",
                agent_name=None,
                text=_safe_content(chunk),
                tool_name=None,
                raw_type=type(chunk).__name__,
            )
        ]

    if isinstance(chunk, AIMessage):
        return [
            NormalizedChunk(
                event_type="assistant",
                agent_name=None,
                text=_safe_content(chunk),
                tool_name=None,
                raw_type=type(chunk).__name__,
            )
        ]

    if isinstance(chunk, ToolMessage):
        return [
            NormalizedChunk(
                event_type="tool",
                agent_name=None,
                text=_safe_content(chunk),
                tool_name=getattr(chunk, "name", None),
                raw_type=type(chunk).__name__,
            )
        ]

    if isinstance(chunk, dict):
        event_type = chunk.get("event", chunk.get("type", "dict_event"))
        text = str(chunk.get("content", chunk.get("text", str(chunk))))
        return [
            NormalizedChunk(
                event_type=str(event_type),
                agent_name=chunk.get("agent_name"),
                text=text,
                tool_name=chunk.get("tool_name"),
                raw_type="dict",
            )
        ]

    if isinstance(chunk, tuple | list):
        results: list[NormalizedChunk] = []
        for item in chunk:
            results.extend(normalize_chunk(item))
        return results

    # Unknown / catch-all
    try:
        text = str(chunk)
    except Exception:
        text = "<unrepresentable>"
    return [
        NormalizedChunk(
            event_type="unknown",
            agent_name=None,
            text=text,
            tool_name=None,
            raw_type=type(chunk).__name__,
        )
    ]


def _safe_content(msg: Any) -> str:
    """Extract text content from a message, safely."""
    try:
        content = getattr(msg, "content", "")
    except Exception:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # content may be a list of content blocks
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            else:
                parts.append(str(block))
        return " ".join(parts)
    return str(content)


def render_chunk(chunk: NormalizedChunk) -> str:
    """Render a NormalizedChunk as a human-readable string."""
    parts = [f"[{chunk.event_type}]"]
    if chunk.agent_name:
        parts.append(f"({chunk.agent_name})")
    if chunk.tool_name:
        parts.append(f"{{{chunk.tool_name}}}")
    if chunk.text:
        parts.append(f" {chunk.text}")
    return "".join(parts)
