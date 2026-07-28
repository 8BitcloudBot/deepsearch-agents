"""07_middleware_skills: Observable middleware and real skills.

Runs fully offline — no API key required.

Usage:
    python -m examples.phase1.runner middleware-skills
"""

import sys
import tempfile
import time
import uuid
from pathlib import Path

from examples.phase1._07_middleware_skills import (
    MiddlewareEvent,
    build_recording_middleware,
    create_skills_middleware,
    list_loaded_skill_names,
)


def main() -> int:
    # --- Middleware demo ---
    print("=== Middleware ===")
    events: list[MiddlewareEvent] = []
    mw = build_recording_middleware(
        events=events,
        clock=time.time,
        request_id_factory=lambda: str(uuid.uuid4())[:8],
    )

    # Simulate a handler call (no real model)
    from unittest.mock import MagicMock

    fake_model = MagicMock()
    fake_model.model_name = "demo-model"
    fake_response = MagicMock()
    fake_response.result = [MagicMock()] * 2

    request = MagicMock()
    request.model = fake_model
    request.messages = [MagicMock()] * 3

    mw.wrap_model_call(request, MagicMock(return_value=fake_response))

    for event in events:
        dur_str = f"{event.duration_ms:.1f}ms" if event.duration_ms else "N/A"
        print(
            f"  [{event.phase}] req={event.request_id} "
            f"model={event.model_name} "
            f"in={event.input_message_count} out={event.output_message_count} "
            f"dur={dur_str}"
        )
    print("  (Middleware events contain no prompts, keys, or full output)")

    # --- Skills demo ---
    print()
    print("=== Skills ===")
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / "source-review"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "# source-review\n\n"
            "**Description:** Reviews source materials for credibility.\n\n"
            "**Trigger:** When verifying claims.\n\n"
            "**Input:** A claim and source documents.\n\n"
            "**Output:** Credibility assessment.\n"
        )
        skills_mw = create_skills_middleware(Path(tmp))
        names = list_loaded_skill_names(skills_mw)
        print(f"  Loaded skills: {names}")
        print(f"  SkillsMiddleware type: {type(skills_mw).__name__}")

    print()
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
