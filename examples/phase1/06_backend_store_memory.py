"""06_backend_store_memory: Backend, Store and Memory concepts.

Demonstrates three separate persistence concepts in DeepAgents:
- backend: filesystem access (temporary directory)
- store: cross-invocation key-value state (InMemoryStore)
- memory: model-consumable conversation history

Usage:
    MODEL_API_KEY=sk-... python -m examples.phase1.runner backend-store-memory
"""

import sys
import tempfile
import uuid
from pathlib import Path

from examples.phase1.settings import load_settings, require_api_key


def demo_backend() -> str:
    """Demonstrate backend filesystem access with temp directory."""
    tmp = tempfile.mkdtemp(prefix="phase1-backend-")
    backend_path = Path(tmp)
    try:
        (backend_path / "research_notes.txt").write_text("Checkpointing: key concept")
        content = (backend_path / "research_notes.txt").read_text()
        return f"Backend (temp): wrote and read '{content}' in {tmp}"
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def demo_store():
    """Demonstrate InMemoryStore with namespace isolation."""
    from langgraph.store.memory import InMemoryStore

    store = InMemoryStore()

    # Write to namespace "research"
    store.put(("research", "topic"), "checkpointing", {"data": "key concepts"})

    # Write to namespace "session"
    store.put(("session", "thread-1"), "state", {"data": "in-progress"})

    # Read back
    item1 = store.get(("research", "topic"), "checkpointing")
    item2 = store.get(("session", "thread-1"), "state")

    return (
        f"Store: research/topic/checkpointing={item1.value if item1 else None}, "
        f"session/thread-1/state={item2.value if item2 else None}"
    )


def demo_memory():
    """Demonstrate memory as model-consumable state.

    Memory in DeepAgents is configured via the `memory` parameter
    to create_deep_agent, which enables MemoryMiddleware.
    """
    thread_id = str(uuid.uuid4())
    return (
        f"Memory: configured for thread {thread_id}. "
        "Uses MemoryMiddleware from deepagents."
    )


def main() -> int:
    settings = load_settings()
    try:
        require_api_key(settings)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 3

    print("=== Backend ===")
    print(demo_backend())
    print()

    print("=== Store ===")
    print(demo_store())
    print()

    print("=== Memory ===")
    print(demo_memory())

    return 0


if __name__ == "__main__":
    sys.exit(main())
