"""06_backend_store_memory: Backend, Store and Memory with real APIs.

Runs fully offline — no API key required.

Usage:
    python -m examples.phase1.runner backend-store-memory
"""

import sys
import tempfile
import uuid
from pathlib import Path

from examples.phase1._06_backend_store_memory import (
    create_filesystem_backend,
    create_memory_middleware,
    create_store,
    get_thread_memory,
    put_thread_memory,
    read_research_note,
    write_research_note,
)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        # Backend
        print("=== Backend ===")
        be = create_filesystem_backend(root)
        write_research_note(be, "/notes/research.md", "# Checkpointing\nKey concept.")
        content = read_research_note(be, "/notes/research.md")
        print(f"  Wrote and read /notes/research.md: {content[:50]}...")

        # Store
        print()
        print("=== Store ===")
        store = create_store()
        tid = str(uuid.uuid4())[:8]
        put_thread_memory(store, thread_id=tid, key="status", value={"state": "ok"})
        val = get_thread_memory(store, thread_id=tid, key="status")
        print(f"  Thread {tid}: stored={val}")

        # Memory
        print()
        print("=== Memory ===")
        write_research_note(
            be, "/memory/main/AGENTS.md", "Research on agent reliability."
        )
        mw = create_memory_middleware(be, source="/memory/main/AGENTS.md")
        print(f"  MemoryMiddleware created: {type(mw).__name__}")

    print()
    print("Done (temp directory cleaned up).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
