"""Phase 1 example runner.

CLI:
    python -m examples.phase1.runner --list
    python -m examples.phase1.runner invoke

Exit codes: 0=success, 1=example error, 2=unknown example, 3=missing API key.
"""

import argparse
import importlib
import sys
from pathlib import Path

EXAMPLES: dict[str, str] = {
    "invoke": "01_invoke.py",
    "stream": "02_stream_chunks.py",
    "dictionary-subagents": "03_dictionary_subagents.py",
    "runnable-subagent": "04_runnable_subagent.py",
    "interrupt-resume": "05_interrupt_resume.py",
    "backend-store-memory": "06_backend_store_memory.py",
    "middleware-skills": "07_middleware_skills.py",
}


def list_examples() -> list[str]:
    """Return the list of known example names."""
    return list(EXAMPLES.keys())


def resolve_example(name: str) -> Path:
    """Resolve an example name to its file path.

    Raises ValueError for unknown names or path traversal attempts.
    """
    if name not in EXAMPLES:
        raise ValueError(f"Unknown example: {name!r}. Known: {list_examples()}")

    filename = EXAMPLES[name]
    base = Path(__file__).resolve().parent
    candidate = (base / filename).resolve()

    # Prevent path traversal
    if not str(candidate).startswith(str(base)):
        raise ValueError(f"Path escape attempt: {name!r}")

    return candidate


def run_example(name: str) -> int:
    """Import and run an example by name. Returns exit code."""
    path = resolve_example(name)
    if not path.exists():
        print(f"Example file not found: {path}", file=sys.stderr)
        return 1

    # Import the module dynamically
    module_name = f"examples.phase1.{path.stem}"
    try:
        mod = importlib.import_module(module_name)
    except ImportError as exc:
        print(f"Failed to import {module_name}: {exc}", file=sys.stderr)
        return 1

    if hasattr(mod, "main"):
        return mod.main()
    print(f"Example {name!r} has no main() function.", file=sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phase 1 DeepAgents capability examples runner"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="List available examples")
    group.add_argument("name", nargs="?", help="Example name to run")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.list:
        for name in list_examples():
            print(name)
        return 0

    if args.name is None:
        parser.print_help()
        return 2

    try:
        resolve_example(args.name)
    except ValueError:
        print(f"Unknown example: {args.name!r}", file=sys.stderr)
        return 2

    # Check for API key requirement (skip for offline examples)
    offline_examples = {
        "interrupt-resume",
        "backend-store-memory",
        "middleware-skills",
    }
    if args.name not in offline_examples:
        try:
            from examples.phase1.settings import load_settings, require_api_key

            settings = load_settings()
            require_api_key(settings)
        except RuntimeError:
            return 3

    return run_example(args.name)


if __name__ == "__main__":
    sys.exit(main())
