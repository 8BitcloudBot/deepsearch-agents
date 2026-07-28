"""04_runnable_subagent: LangGraph/Runnable-based sub-agent example.

Demonstrates CompiledSubAgent wrapping a Runnable (LangGraph graph).

Usage:
    MODEL_API_KEY=sk-... python -m examples.phase1.runner runnable-subagent
"""

import sys

from examples.phase1.events import normalize_chunk, render_chunk
from examples.phase1.settings import load_settings, require_api_key

SYSTEM_PROMPT = (
    "You are a research coordinator. Delegate analytical tasks to the "
    "analysis-engine sub-agent when needed."
)
USER_INPUT = "Analyze the trade-offs between checkpointing and human approval."


def build_runnable_subagent():
    """Build a minimal LangGraph-based Runnable sub-agent."""
    from deepagents.middleware.subagents import CompiledSubAgent
    from langgraph.graph import END, StateGraph
    from langgraph.graph.state import CompiledStateGraph

    class AnalysisState(dict):
        messages: list

    def analyze(state: AnalysisState) -> AnalysisState:
        last_msg = state.get("messages", [{}])[-1] if state.get("messages") else {}
        content = last_msg.get("content", "") if isinstance(last_msg, dict) else ""
        response = f"Analysis: {content[:100]}... [analysis complete]"
        state["messages"] = state.get("messages", []) + [
            {"role": "assistant", "content": response}
        ]
        return state

    builder = StateGraph(AnalysisState)
    builder.add_node("analyze", analyze)
    builder.set_entry_point("analyze")
    builder.add_edge("analyze", END)
    graph: CompiledStateGraph = builder.compile()

    sub: CompiledSubAgent = {
        "name": "analysis-engine",
        "description": "Performs structured analysis of trade-offs.",
        "runnable": graph,
    }
    return sub


def main() -> int:
    settings = load_settings()
    try:
        api_key = require_api_key(settings)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 3

    from deepagents import create_deep_agent
    from langchain_openai import ChatOpenAI

    model_kwargs: dict = {"model": settings.model_name, "api_key": api_key}
    if settings.base_url:
        model_kwargs["base_url"] = settings.base_url

    model = ChatOpenAI(**model_kwargs)
    runnable_sub = build_runnable_subagent()

    agent = create_deep_agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        subagents=[runnable_sub],
    )

    print(f"Main agent with runnable sub-agent: {runnable_sub['name']}")

    result = agent.invoke({"messages": [{"role": "user", "content": USER_INPUT}]})
    messages = result.get("messages", [])
    for msg in messages:
        normalized = normalize_chunk(msg)
        for nc in normalized:
            print(render_chunk(nc))

    return 0


if __name__ == "__main__":
    sys.exit(main())
