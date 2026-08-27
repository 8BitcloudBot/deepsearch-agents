"""03_dictionary_subagents: Two declarative sub-agents example.

Demonstrates SubAgent TypedDict with name, description, system_prompt.
Sub-agents: framework-researcher, risk-reviewer.

Usage:
    MODEL_API_KEY=sk-... python -m examples.phase1.runner dictionary-subagents
"""

import sys

from examples.phase1.events import normalize_chunk, render_chunk
from examples.phase1.settings import load_settings, require_api_key

SYSTEM_PROMPT = (
    "You are a research coordinator. Delegate work to sub-agents when appropriate."
)
USER_INPUT = "Compare checkpointing and human approval as reliability mechanisms."


def build_subagents():
    """Return two declarative sub-agents compatible with DeepAgents."""
    from deepagents.middleware.subagents import SubAgent

    framework_researcher: SubAgent = {
        "name": "framework-researcher",
        "description": "Summarizes framework capabilities from provided context.",
        "system_prompt": (
            "You are a framework researcher. When asked about a mechanism, "
            "summarize what it does and which frameworks support it."
        ),
    }

    risk_reviewer: SubAgent = {
        "name": "risk-reviewer",
        "description": "Lists implementation risks for a given approach.",
        "system_prompt": (
            "You are a risk reviewer. When given a reliability mechanism, "
            "list the key implementation risks and failure modes."
        ),
    }

    return [framework_researcher, risk_reviewer]


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
    subagents = build_subagents()
    agent = create_deep_agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        subagents=subagents,
    )

    print(f"Main agent with {len(subagents)} sub-agents:")
    for sa in subagents:
        print(f"  - {sa['name']}: {sa['description']}")

    result = agent.invoke({"messages": [{"role": "user", "content": USER_INPUT}]})
    messages = result.get("messages", [])
    for msg in messages:
        normalized = normalize_chunk(msg)
        for nc in normalized:
            print(render_chunk(nc))

    return 0


if __name__ == "__main__":
    sys.exit(main())
