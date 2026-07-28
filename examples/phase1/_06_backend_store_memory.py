"""Backend/Store/Memory with real DeepAgents 0.6.12 APIs.

Testable interfaces. Used by 06_backend_store_memory.py and tests.
"""

from pathlib import Path

from deepagents.backends.filesystem import FilesystemBackend
from deepagents.middleware.memory import MemoryMiddleware
from langgraph.store.memory import InMemoryStore


def create_filesystem_backend(root: Path) -> FilesystemBackend:
    """Create a real FilesystemBackend scoped to root."""
    return FilesystemBackend(root_dir=str(root), virtual_mode=True)


def write_research_note(backend: FilesystemBackend, path: str, content: str) -> None:
    """Write a research note via the backend."""
    backend.write(path, content)


def read_research_note(backend: FilesystemBackend, path: str) -> str:
    """Read a research note via the backend."""
    result = backend.read(path)
    if result.error:
        raise OSError(f"Read error: {result.error}")
    if result.file_data:
        return result.file_data["content"]
    return ""


def create_store() -> InMemoryStore:
    """Create a real InMemoryStore."""
    return InMemoryStore()


def put_thread_memory(store, *, thread_id: str, key: str, value: dict) -> None:
    """Store a value under (phase1, threads, thread_id)."""
    store.put(("phase1", "threads", thread_id), key, value)


def get_thread_memory(store, *, thread_id: str, key: str) -> dict | None:
    """Retrieve a stored value by thread_id and key."""
    item = store.get(("phase1", "threads", thread_id), key)
    return item.value if item else None


def create_memory_middleware(backend, *, source: str) -> MemoryMiddleware:
    """Create a MemoryMiddleware backed by the given backend and source file."""
    return MemoryMiddleware(backend=backend, sources=[source])
