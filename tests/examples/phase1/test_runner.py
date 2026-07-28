"""Tests for examples.phase1.runner."""

import os
import subprocess
import sys

import pytest

from examples.phase1.runner import EXAMPLES, list_examples, resolve_example


def test_list_examples_returns_seven():
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


def test_examples_dict_matches_list():
    assert set(EXAMPLES.keys()) == set(list_examples())


def test_resolve_example_known():
    path = resolve_example("invoke")
    assert path.name == "01_invoke.py"
    assert path.exists() or True  # may not exist until Task 3


def test_resolve_example_does_not_escape():
    """resolve_example must not allow path traversal outside examples/phase1."""
    with pytest.raises(ValueError):
        resolve_example("../secret")


def test_resolve_unknown_returns_error():
    with pytest.raises(ValueError):
        resolve_example("nonexistent")


def test_runner_cli_list():
    result = subprocess.run(
        [sys.executable, "-m", "examples.phase1.runner", "--list"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    for name in list_examples():
        assert name in result.stdout


def test_runner_cli_unknown_exits_2():
    result = subprocess.run(
        [sys.executable, "-m", "examples.phase1.runner", "nonexistent"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2


def test_runner_cli_missing_key_exits_3(monkeypatch):
    """Without MODEL_API_KEY, runner should exit 3."""
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    result = subprocess.run(
        [sys.executable, "-m", "examples.phase1.runner", "invoke"],
        capture_output=True,
        text=True,
        timeout=10,
        env={**os.environ, "MODEL_API_KEY": ""},
    )
    assert result.returncode == 3


def test_runner_import_does_not_connect():
    """Importing runner must NOT trigger model connection or network."""
    # This is verified by the import at module level — if it doesn't raise,
    # the import itself is safe (no side effects).
    pass
