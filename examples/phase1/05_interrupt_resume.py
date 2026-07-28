"""05_interrupt_resume: Interrupt, approval and resume example.

Demonstrates LangGraph interrupt() + Command(resume=...) with MemorySaver.

Usage:
    MODEL_API_KEY=sk-... python -m examples.phase1.runner interrupt-resume
"""

import sys
import uuid
from typing import Any

from examples.phase1.settings import load_settings, require_api_key

SYSTEM_PROMPT = (
    "You are a research agent. Before executing a risky action, request human approval."
)


def build_graph_with_interrupt():
    """Build a LangGraph graph that uses interrupt() for approval."""
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, StateGraph

    class RiskState(dict):
        messages: list
        approved: bool
        risk_action: str
        risk_level: str
        risk_reason: str

    def propose_risk(state: RiskState) -> RiskState:
        """Propose a risk action and interrupt for human approval."""
        from langgraph.types import interrupt

        state["risk_action"] = "delete_old_checkpoints"
        state["risk_reason"] = "Cleanup of stale checkpoint data to free disk space"
        state["risk_level"] = "medium"

        # Interrupt for human approval
        approval = interrupt(
            {
                "action": state["risk_action"],
                "reason": state["risk_reason"],
                "risk_level": state["risk_level"],
            }
        )
        state["approved"] = bool(approval.get("approved", False))
        return state

    def execute_if_approved(state: RiskState) -> RiskState:
        if state.get("approved"):
            state["messages"] = state.get("messages", []) + [
                {"role": "assistant", "content": "Risk action approved and executed."}
            ]
        return state

    def handle_rejection(state: RiskState) -> RiskState:
        state["messages"] = state.get("messages", []) + [
            {
                "role": "assistant",
                "content": "Risk action rejected. No changes made.",
            }
        ]
        return state

    def should_execute(state: RiskState) -> str:
        return "execute" if state.get("approved") else "reject"

    builder = StateGraph(RiskState)
    builder.add_node("propose", propose_risk)
    builder.add_node("execute", execute_if_approved)
    builder.add_node("reject", handle_rejection)
    builder.set_entry_point("propose")
    builder.add_conditional_edges(
        "propose",
        should_execute,
        {
            "execute": "execute",
            "reject": "reject",
        },
    )
    builder.add_edge("execute", END)
    builder.add_edge("reject", END)

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)


def run_interrupt_flow(approve: bool) -> dict[str, Any]:
    """Run the interrupt flow with approve=True or False.

    Returns the final state after resumption.
    """
    from langgraph.types import Command

    graph = build_graph_with_interrupt()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    # First invocation — will hit interrupt
    initial_state: dict[str, Any] = {
        "messages": [{"role": "user", "content": "Clean up old checkpoint data."}],
        "approved": False,
        "risk_action": "",
        "risk_level": "",
        "risk_reason": "",
    }

    # Run until interrupt
    _events = list(graph.stream(initial_state, config, stream_mode="updates"))
    # Second invocation with resume
    result = graph.invoke(
        Command(resume={"approved": approve}),
        config,
    )
    return result


def main() -> int:
    settings = load_settings()
    try:
        require_api_key(settings)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 3

    print("=== Interrupt & Resume: Approved ===")
    result_approved = run_interrupt_flow(approve=True)
    messages = result_approved.get("messages", [])
    for msg in messages:
        content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
        print(f"  {content}")

    print()
    print("=== Interrupt & Resume: Rejected ===")
    result_rejected = run_interrupt_flow(approve=False)
    messages = result_rejected.get("messages", [])
    for msg in messages:
        content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
        print(f"  {content}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
