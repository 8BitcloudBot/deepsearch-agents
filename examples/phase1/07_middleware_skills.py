"""07_middleware_skills: Observable middleware and real skills.

Runs fully offline — loads source-review skill through SkillsMiddleware.

Usage:
    python -m examples.phase1.runner middleware-skills
"""

import sys
import time
import uuid
from pathlib import Path
from unittest.mock import MagicMock

from langgraph.runtime import Runtime

from examples.phase1._07_middleware_skills import (
    MiddlewareEvent,
    build_recording_middleware,
    create_skills_middleware,
    load_skills_metadata,
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

    # --- Skills demo (real SkillsMiddleware loading) ---
    print()
    print("=== Skills ===")
    skills_root = Path(__file__).resolve().parent / "skills"
    skills_mw = create_skills_middleware(skills_root)
    metadata = load_skills_metadata(skills_mw, runtime=Runtime())

    if not metadata:
        print("ERROR: No skills loaded from project skills directory.", file=sys.stderr)
        return 1

    for m in metadata:
        print(f"  - {m['name']}: {m['description']}")

    print()
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
