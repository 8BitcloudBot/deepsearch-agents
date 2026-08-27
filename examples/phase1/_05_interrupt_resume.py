"""Interrupt/resume graph with testable side_effects injection.

This module provides the LangGraph graph used by 05_interrupt_resume.py
and the behavioral tests. Not intended for direct execution.
"""

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

# Thread-id → side_effects list registry (for testability)
_SIDE_EFFECTS_REGISTRY: dict[str, list[str]] = {}


class RiskState(dict):
    """State for the risk-approval graph."""

    messages: list
    approved: bool
    risk_action: str
    risk_level: str
    risk_reason: str
    _side_effects: list[str]
    _thread_id: str


def build_graph_with_interrupt():
    """Build a LangGraph graph that uses interrupt() for risk approval.

    The graph has two conditional paths after interrupt:
    - approve → execute (records side_effect)
    - reject → skip
    """
    builder = StateGraph(RiskState)

    def propose_risk(state: RiskState) -> RiskState:
        state["risk_action"] = "delete_old_checkpoints"
        state["risk_reason"] = "Cleanup of stale checkpoint data to free disk space"
        state["risk_level"] = "medium"
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
        tid = state.get("_thread_id", "")
        se = _SIDE_EFFECTS_REGISTRY.get(tid, [])
        if state.get("approved"):
            se.append("execute:delete_old_checkpoints")
        state["_side_effects"] = se
        return state

    def handle_rejection(state: RiskState) -> RiskState:
        return state

    def should_execute(state: RiskState) -> str:
        return "execute" if state.get("approved") else "reject"

    builder.add_node("propose", propose_risk)
    builder.add_node("execute", execute_if_approved)
    builder.add_node("reject", handle_rejection)
    builder.set_entry_point("propose")
    builder.add_conditional_edges(
        "propose",
        should_execute,
        {"execute": "execute", "reject": "reject"},
    )
    builder.add_edge("execute", END)
    builder.add_edge("reject", END)

    return builder.compile(checkpointer=MemorySaver())


def start_interrupt_flow(
    graph,
    *,
    thread_id: str,
    side_effects: list[str],
) -> dict[str, Any]:
    """Start the flow. Will hit interrupt. Returns interrupted state dict.

    Registers side_effects list for the thread_id so the graph can
    mutate it directly via the registry.
    """
    _SIDE_EFFECTS_REGISTRY[thread_id] = side_effects

    config = {"configurable": {"thread_id": thread_id}}
    initial_state: dict[str, Any] = {
        "messages": [{"role": "user", "content": "Clean up old checkpoint data."}],
        "approved": False,
        "risk_action": "",
        "risk_level": "",
        "risk_reason": "",
        "_thread_id": thread_id,
    }

    result = None
    for event in graph.stream(initial_state, config, stream_mode="updates"):
        result = event

    state = graph.get_state(config)
    if state and state.interrupts:
        return {"__interrupt__": state.interrupts}

    return result if result else {}


def resume_interrupt_flow(
    graph,
    *,
    thread_id: str,
    approved: bool,
) -> dict[str, Any]:
    """Resume a previously interrupted flow with approve=True/False."""
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(Command(resume={"approved": approved}), config)
    return result
