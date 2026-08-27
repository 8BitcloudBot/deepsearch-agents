"""Integration smoke tests — require MODEL_API_KEY.

Only executes minimal invoke & stream smoke when MODEL_API_KEY is set.
Otherwise skips all tests with a clear reason.
"""

import os
import subprocess
import sys

import pytest

pytestmark = pytest.mark.integration

requires_api_key = pytest.mark.skipif(
    not os.environ.get("MODEL_API_KEY"),
    reason="MODEL_API_KEY not set — skipping real model smoke test",
)


@requires_api_key
def test_smoke_invoke():
    """Real model invoke smoke: calls runner invoke and expects exit 0."""
    result = subprocess.run(
        [sys.executable, "-m", "examples.phase1.runner", "invoke"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    # exit 0 means success; exit 3 means missing key (shouldn't happen)
    assert result.returncode == 0, (
        f"invoke smoke failed (exit={result.returncode}):\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


@requires_api_key
def test_smoke_stream():
    """Real model stream smoke: calls runner stream and expects exit 0."""
    result = subprocess.run(
        [sys.executable, "-m", "examples.phase1.runner", "stream"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"stream smoke failed (exit={result.returncode}):\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
