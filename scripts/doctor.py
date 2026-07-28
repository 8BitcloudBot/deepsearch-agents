#!/usr/bin/env python3
"""Phase 0 environment doctor.

Usage:
    python scripts/doctor.py --offline    # Check offline requirements
    python scripts/doctor.py --mysql      # Check MySQL connectivity & health table
"""

import argparse
import os
import sys

MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "root")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "research_copilot")


def check_offline() -> int:
    """Check offline prerequisites (no external services needed)."""
    print("[doctor] Running offline checks ...")
    checks_ok = True

    # Check Python version
    py_version = sys.version_info
    if py_version.major == 3 and py_version.minor == 12:
        print(f"  [OK] Python {py_version.major}.{py_version.minor}.{py_version.micro}")
    else:
        print(
            f"  [FAIL] Need Python 3.12, got {py_version.major}.{py_version.minor}"
        )
        checks_ok = False

    if checks_ok:
        print("[doctor] All offline checks passed.")
        return 0
    else:
        print("[doctor] Offline checks failed.", file=sys.stderr)
        return 1


def check_mysql() -> int:
    """Check MySQL connectivity and health table.

    mysql-connector-python is imported lazily; if not installed,
    doctor reports the missing dependency and exits non-zero.
    """
    print("[doctor] Running MySQL checks ...")

    try:
        import mysql.connector  # noqa: F401 — optional dependency
    except ImportError:
        print(
            "[doctor] mysql-connector-python is not installed. "
            "Install it with: uv sync --extra dev",
            file=sys.stderr,
        )
        return 2

    import mysql.connector

    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            connect_timeout=5,
        )
    except mysql.connector.Error as exc:
        print(f"  [FAIL] Cannot connect to MySQL: {exc}", file=sys.stderr)
        print(
            "[doctor] Is MySQL running? Try: docker compose up -d mysql",
            file=sys.stderr,
        )
        return 3

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM phase_0_health")
        row = cursor.fetchone()
        if row and row[0] == "ok":
            print("  [OK] phase_0_health table contains 'ok'")
        else:
            print(
                f"  [FAIL] phase_0_health table has unexpected value: {row}",
                file=sys.stderr,
            )
            return 4
    except mysql.connector.Error as exc:
        print(f"  [FAIL] Query failed: {exc}", file=sys.stderr)
        return 5
    finally:
        cursor.close()
        conn.close()

    print("[doctor] All MySQL checks passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 0 environment doctor")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--offline", action="store_true", help="Run offline checks only"
    )
    group.add_argument(
        "--mysql", action="store_true", help="Run MySQL connectivity check"
    )
    args = parser.parse_args()

    if args.offline:
        return check_offline()
    if args.mysql:
        return check_mysql()

    return 1


if __name__ == "__main__":
    sys.exit(main())
