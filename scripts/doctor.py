#!/usr/bin/env python3
"""Check local prerequisites for the conversation product."""

import argparse
import sys


def check_offline() -> int:
    """Check prerequisites that do not contact external providers."""
    print("[doctor] Running offline checks ...")
    version = sys.version_info
    if version.major != 3 or version.minor != 12:
        print(
            f"  [FAIL] Need Python 3.12, got {version.major}.{version.minor}",
            file=sys.stderr,
        )
        print("[doctor] Offline checks failed.", file=sys.stderr)
        return 1
    print(f"  [OK] Python {version.major}.{version.minor}.{version.micro}")
    print("[doctor] All offline checks passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Conversation product doctor")
    parser.add_argument(
        "--offline", action="store_true", help="Run local prerequisite checks"
    )
    args = parser.parse_args()
    if not args.offline:
        parser.error("--offline is required")
    return check_offline()


if __name__ == "__main__":
    sys.exit(main())
