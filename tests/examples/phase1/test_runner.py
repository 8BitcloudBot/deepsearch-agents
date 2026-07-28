"""Tests for examples.phase1.runner."""

import os
import socket
import subprocess
import sys

import pytest

from examples.phase1.runner import EXAMPLES, list_examples, resolve_example


class TestListing:
    def test_list_examples_returns_seven(self):
        names = list_examples()
        assert len(names) == 7
        expected = {
            "invoke",
            "stream",
            "dictionary-subagents",
            "runnable-subagent",
            "interrupt-resume",
            "backend-store-memory",
            "middleware-skills",
        }
        assert set(names) == expected

    def test_examples_dict_matches_list(self):
        assert set(EXAMPLES.keys()) == set(list_examples())


class TestResolve:
    def test_resolve_example_known(self):
        path = resolve_example("invoke")
        assert path.name == "01_invoke.py"
        assert path.exists(), f"File must exist: {path}"

    def test_resolve_example_known_stream(self):
        path = resolve_example("stream")
        assert path.name == "02_stream_chunks.py"
        assert path.exists()

    def test_resolve_example_does_not_escape(self):
        with pytest.raises(ValueError):
            resolve_example("../secret")

    def test_resolve_unknown_returns_error(self):
        with pytest.raises(ValueError):
            resolve_example("nonexistent")


class TestRunnerCLI:
    def test_list(self):
        result = subprocess.run(
            [sys.executable, "-m", "examples.phase1.runner", "--list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        for name in list_examples():
            assert name in result.stdout

    def test_unknown_exits_2(self):
        result = subprocess.run(
            [sys.executable, "-m", "examples.phase1.runner", "nonexistent"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 2

    def test_invoke_missing_key_exits_3(self):
        result = subprocess.run(
            [sys.executable, "-m", "examples.phase1.runner", "invoke"],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "MODEL_API_KEY": ""},
        )
        assert result.returncode == 3

    def test_stream_missing_key_exits_3(self):
        result = subprocess.run(
            [sys.executable, "-m", "examples.phase1.runner", "stream"],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "MODEL_API_KEY": ""},
        )
        assert result.returncode == 3

    def test_interrupt_resume_no_key_exits_0(self):
        result = subprocess.run(
            [sys.executable, "-m", "examples.phase1.runner", "interrupt-resume"],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "MODEL_API_KEY": ""},
        )
        assert result.returncode == 0

    def test_backend_store_memory_no_key_exits_0(self):
        result = subprocess.run(
            [sys.executable, "-m", "examples.phase1.runner", "backend-store-memory"],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "MODEL_API_KEY": ""},
        )
        assert result.returncode == 0

    def test_middleware_skills_no_key_exits_0(self):
        result = subprocess.run(
            [sys.executable, "-m", "examples.phase1.runner", "middleware-skills"],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "MODEL_API_KEY": ""},
        )
        assert result.returncode == 0


class TestImportSafety:
    def test_import_does_not_connect(self):
        """Importing runner must NOT trigger network connections."""
        # Block socket creation during import
        original_socket = socket.socket

        def guarded_socket(*args, **kwargs):
            pytest.fail("Socket creation detected during import")

        socket.socket = guarded_socket
        try:
            import importlib

            importlib.reload(sys.modules["examples.phase1.runner"])
        finally:
            socket.socket = original_socket
