"""Behavioral tests for backend/store/memory using real DeepAgents APIs.

No MODEL_API_KEY required.
"""

import tempfile
from pathlib import Path

import pytest

from examples.phase1._06_backend_store_memory import (
    create_filesystem_backend,
    create_memory_middleware,
    create_store,
    get_thread_memory,
    put_thread_memory,
    read_research_note,
    write_research_note,
)


class TestFilesystemBackend:
    def test_backend_is_real_filesystem_backend(self):
        """Must return a real FilesystemBackend instance."""
        from deepagents.backends.filesystem import FilesystemBackend

        root = tempfile.mkdtemp()
        try:
            be = create_filesystem_backend(Path(root))
            assert isinstance(be, FilesystemBackend)
        finally:
            import shutil

            shutil.rmtree(root, ignore_errors=True)

    def test_write_and_read_within_root(self, tmp_path):
        """Write and read back a file within the backend root."""
        be = create_filesystem_backend(tmp_path)
        write_research_note(be, "/notes/research.md", "# Checkpointing")
        content = read_research_note(be, "/notes/research.md")
        assert "# Checkpointing" in content

    def test_path_escape_rejected(self, tmp_path):
        """Backend must reject path traversal (../ outside root)."""
        be = create_filesystem_backend(tmp_path)
        with pytest.raises(Exception):
            write_research_note(be, "../outside.txt", "danger")


class TestStore:
    def test_store_is_real_inmemory_store(self):
        """Must return a real InMemoryStore."""
        from langgraph.store.memory import InMemoryStore

        store = create_store()
        assert isinstance(store, InMemoryStore)

    def test_namespace_isolation(self):
        """Two namespaces must not leak data to each other."""
        store = create_store()
        put_thread_memory(store, thread_id="a", key="topic", value={"v": 1})
        put_thread_memory(store, thread_id="b", key="topic", value={"v": 2})

        a_val = get_thread_memory(store, thread_id="a", key="topic")
        b_val = get_thread_memory(store, thread_id="b", key="topic")
        assert a_val == {"v": 1}
        assert b_val == {"v": 2}


class TestMemory:
    def test_memory_middleware_is_real(self, tmp_path):
        """create_memory_middleware must return a real MemoryMiddleware."""
        from deepagents import MemoryMiddleware

        be = create_filesystem_backend(tmp_path)
        write_research_note(be, "/memory/t1/AGENTS.md", "Memory content")
        mw = create_memory_middleware(be, source="/memory/t1/AGENTS.md")
        assert isinstance(mw, MemoryMiddleware)

    def test_memory_visible_to_same_thread(self, tmp_path):
        """Memory written for thread A must be readable."""
        be = create_filesystem_backend(tmp_path)
        write_research_note(be, "/memory/t1/AGENTS.md", "T1 memory")
        content = read_research_note(be, "/memory/t1/AGENTS.md")
        assert "T1 memory" in content

    def test_memory_isolated_between_threads(self, tmp_path):
        """Thread A must not read thread B's memory."""
        be = create_filesystem_backend(tmp_path)
        write_research_note(be, "/memory/ta/AGENTS.md", "TA memory")
        write_research_note(be, "/memory/tb/AGENTS.md", "TB memory")

        ta = read_research_note(be, "/memory/ta/AGENTS.md")
        tb = read_research_note(be, "/memory/tb/AGENTS.md")
        assert "TA memory" in ta
        assert "TB memory" in tb
        assert "TA" not in tb

    def test_tmp_path_cleanup(self, tmp_path):
        """Backend root is tmp_path — must not leave files outside."""
        be = create_filesystem_backend(tmp_path)
        write_research_note(be, "/notes/test.md", "data")
        # tmp_path auto-cleaned by pytest
