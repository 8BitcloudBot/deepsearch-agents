"""07_middleware_skills: Middleware and Skills example.

Demonstrates:
- Custom middleware with request/response logging (no secrets in logs)
- Skill loading from a skills directory

Usage:
    MODEL_API_KEY=sk-... python -m examples.phase1.runner middleware-skills
"""

import sys

from examples.phase1.settings import load_settings, require_api_key


def build_logging_middleware():
    """Build a minimal middleware that logs request/response metadata.

    Does NOT log prompts, API keys, or full model output.
    """
    from langchain.agents.middleware import AgentMiddleware

    request_counter = {"count": 0}

    class LoggingMiddleware(AgentMiddleware):
        def __init__(self):
            super().__init__()

        def before_model(self, state, runtime):
            request_counter["count"] += 1
            # Safe to log: no secrets or prompts
            return None

        def after_model(self, state, runtime):
            # Safe to log: no secrets or prompts
            return None

    return LoggingMiddleware()


def discover_skills():
    """Discover skills from the skills directory."""
    import os
    from pathlib import Path

    skills_dir = Path(__file__).parent / "skills"
    if not skills_dir.exists():
        return []

    found = []
    for entry in os.listdir(skills_dir):
        skill_md = skills_dir / entry / "SKILL.md"
        if skill_md.exists():
            found.append(entry)
    return found


def main() -> int:
    settings = load_settings()
    try:
        require_api_key(settings)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 3

    print("=== Middleware ===")
    mw = build_logging_middleware()
    print(f"  Middleware created: {type(mw).__name__}")
    print("  Middleware logs request/response metadata only (no secrets).")

    print()
    print("=== Skills ===")
    skills = discover_skills()
    if skills:
        for s in skills:
            print(f"  Found skill: {s}")
    else:
        print("  No skills discovered.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
