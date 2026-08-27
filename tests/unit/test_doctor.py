"""Tests for the environment doctor — Phase 0 contract."""

import importlib
import subprocess
import sys


def test_doctor_offline_exits_zero():
    """--offline mode checks the local application prerequisites."""
    result = subprocess.run(
        [sys.executable, "scripts/doctor.py", "--offline"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "offline" in result.stdout.lower() or "ok" in result.stdout.lower()


def test_doctor_has_no_structured_data_mode():
    result = subprocess.run(
        [sys.executable, "scripts/doctor.py", "--mysql"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "mysql-connector" not in (result.stdout + result.stderr).lower()


def test_doctor_sh_delegates_to_python():
    """doctor.sh must delegate to doctor.py and pass arguments."""
    result = subprocess.run(
        ["bash", "scripts/doctor.sh", "--offline"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_doctor_module_has_no_structured_data_configuration():
    doctor = importlib.import_module("scripts.doctor")
    doctor = importlib.reload(doctor)
    assert not hasattr(doctor, "check_mysql")
    assert not hasattr(doctor, "MYSQL_PORT")
