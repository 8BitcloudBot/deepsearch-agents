"""Tests for the environment doctor — Phase 0 contract."""

import importlib
import subprocess
import sys

# Importing the doctor module may fail without mysql-connector-python;
# tests must mock the optional import or work in offline mode.
# We test the CLI via subprocess for end-to-end behavior.


def test_doctor_offline_exits_zero():
    """--offline mode must exit 0 without MySQL."""
    result = subprocess.run(
        [sys.executable, "scripts/doctor.py", "--offline"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "offline" in result.stdout.lower() or "ok" in result.stdout.lower()


def test_doctor_mysql_unavailable_exits_nonzero():
    """--mysql mode without running MySQL must exit non-zero."""
    result = subprocess.run(
        [sys.executable, "scripts/doctor.py", "--mysql"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    # MySQL is not running — should exit non-zero
    assert result.returncode != 0, (
        f"Expected non-zero exit without MySQL, got {result.returncode}. "
        f"stdout: {result.stdout}, stderr: {result.stderr}"
    )


def test_doctor_sh_delegates_to_python():
    """doctor.sh must delegate to doctor.py and pass arguments."""
    result = subprocess.run(
        ["bash", "scripts/doctor.sh", "--offline"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_doctor_uses_dedicated_host_port_by_default(monkeypatch):
    """Research Copilot must avoid the common host MySQL port by default."""
    monkeypatch.delenv("MYSQL_PORT", raising=False)
    doctor = importlib.import_module("scripts.doctor")
    doctor = importlib.reload(doctor)
    assert doctor.MYSQL_PORT == 3307


def test_doctor_allows_explicit_mysql_port_override(monkeypatch):
    """An explicit MYSQL_PORT keeps the project usable in custom environments."""
    monkeypatch.setenv("MYSQL_PORT", "13306")
    doctor = importlib.import_module("scripts.doctor")
    doctor = importlib.reload(doctor)
    assert doctor.MYSQL_PORT == 13306
