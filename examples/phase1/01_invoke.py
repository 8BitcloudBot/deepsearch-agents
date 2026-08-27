"""01_invoke: Basic agent invocation example.

Uses create_deep_agent with a fixed prompt and returns the final
assistant text.

Usage:
    MODEL_API_KEY=sk-... python -m examples.phase1.runner invoke
"""

import sys

from examples.phase1.settings import load_settings, require_api_key

SYSTEM_PROMPT = "You are a concise research assistant. Answer with one sentence."
USER_INPUT = "Explain why checkpointing matters for long-running agents."


def main() -> int:
    """Run the invoke example. Returns exit code."""
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
    agent = create_deep_agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
    )

    result = agent.invoke({"messages": [{"role": "user", "content": USER_INPUT}]})

    # Extract final assistant message
    messages = result.get("messages", [])
    for msg in reversed(messages):
        content = getattr(msg, "content", "")
        if content and getattr(msg, "type", "") == "ai":
            print(content)
            return 0

    print("No assistant response found.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
