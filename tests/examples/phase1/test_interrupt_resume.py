"""Behavioral tests for interrupt/resume flow.

No MODEL_API_KEY required — these tests use MemorySaver + LangGraph interrupt.
"""

from examples.phase1._05_interrupt_resume import (
    build_graph_with_interrupt,
    resume_interrupt_flow,
    start_interrupt_flow,
)


class TestFirstRun:
    def test_first_run_exposes_interrupt_payload(self):
        """First execution must produce an interrupt with action/reason/risk_level."""
        graph = build_graph_with_interrupt()
        side_effects: list[str] = []
        result = start_interrupt_flow(graph, thread_id="t1", side_effects=side_effects)

        interrupt_data = result.get("__interrupt__")
        assert interrupt_data is not None, f"Expected interrupt, got: {result}"
        assert interrupt_data[0].value["action"] == "delete_old_checkpoints"
        assert "stale" in interrupt_data[0].value["reason"]
        assert interrupt_data[0].value["risk_level"] == "medium"

    def test_interrupt_pauses_execution(self):
        """Side effects must NOT be recorded before approval."""
        graph = build_graph_with_interrupt()
        side_effects: list[str] = []
        start_interrupt_flow(graph, thread_id="t2", side_effects=side_effects)
        assert side_effects == [], "No side effects before approval"


class TestApprove:
    def test_approve_executes_risk_action_once(self):
        """Approval must append exactly one side_effect entry."""
        graph = build_graph_with_interrupt()
        side_effects: list[str] = []
        start_interrupt_flow(graph, thread_id="t3", side_effects=side_effects)
        resume_interrupt_flow(graph, thread_id="t3", approved=True)
        assert side_effects == ["execute:delete_old_checkpoints"]


class TestReject:
    def test_reject_does_not_execute_risk_action(self):
        """Rejection must NOT append any side_effects."""
        graph = build_graph_with_interrupt()
        side_effects: list[str] = []
        start_interrupt_flow(graph, thread_id="t4", side_effects=side_effects)
        resume_interrupt_flow(graph, thread_id="t4", approved=False)
        assert side_effects == []


class TestThreadIsolation:
    def test_different_thread_ids_are_isolated(self):
        """Thread A's state must not affect thread B."""
        graph = build_graph_with_interrupt()

        # Thread A: approve
        a_effects: list[str] = []
        start_interrupt_flow(graph, thread_id="thread-a", side_effects=a_effects)
        resume_interrupt_flow(graph, thread_id="thread-a", approved=True)
        assert a_effects == ["execute:delete_old_checkpoints"]

        # Thread B: reject — must start fresh
        b_effects: list[str] = []
        start_interrupt_flow(graph, thread_id="thread-b", side_effects=b_effects)
        resume_interrupt_flow(graph, thread_id="thread-b", approved=False)
        assert b_effects == []


class TestIdempotentResume:
    def test_repeated_resume_does_not_duplicate_side_effect(self):
        """Repeating resume on the same thread must not re-execute side effect."""
        graph = build_graph_with_interrupt()
        side_effects: list[str] = []
        start_interrupt_flow(graph, thread_id="t5", side_effects=side_effects)
        resume_interrupt_flow(graph, thread_id="t5", approved=True)
        # Second resume — should be no-op
        resume_interrupt_flow(graph, thread_id="t5", approved=True)
        assert side_effects.count("execute:delete_old_checkpoints") == 1
