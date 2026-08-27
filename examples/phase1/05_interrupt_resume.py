"""05_interrupt_resume: Interrupt, approval and resume example.

Now runs fully offline — no model calls, no API key required.

Usage:
    python -m examples.phase1.runner interrupt-resume
"""

import sys
import uuid

from examples.phase1._05_interrupt_resume import (
    build_graph_with_interrupt,
    resume_interrupt_flow,
    start_interrupt_flow,
)


def main() -> int:
    print("=== Interrupt & Resume (offline) ===")
    print()

    # --- Approved flow ---
    print("--- Approved ---")
    graph = build_graph_with_interrupt()
    tid_approved = f"demo-{uuid.uuid4().hex[:8]}"
    effects: list[str] = []
    start_interrupt_flow(graph, thread_id=tid_approved, side_effects=effects)
    print(f"  Interrupted: thread={tid_approved}")
    resume_interrupt_flow(graph, thread_id=tid_approved, approved=True)
    print(f"  Approved. Side effects: {effects}")

    # --- Rejected flow ---
    print()
    print("--- Rejected ---")
    graph2 = build_graph_with_interrupt()
    tid_rejected = f"demo-{uuid.uuid4().hex[:8]}"
    effects2: list[str] = []
    start_interrupt_flow(graph2, thread_id=tid_rejected, side_effects=effects2)
    resume_interrupt_flow(graph2, thread_id=tid_rejected, approved=False)
    print(f"  Rejected. Side effects: {effects2}")

    print()
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
