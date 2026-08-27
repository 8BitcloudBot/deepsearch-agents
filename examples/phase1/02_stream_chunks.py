"""02_stream_chunks: Streaming agent with event normalization.

Uses create_deep_agent.stream() and normalizes chunks via events.py.

Usage:
    MODEL_API_KEY=sk-... python -m examples.phase1.runner stream
"""

import sys

from examples.phase1.events import normalize_chunk, render_chunk
from examples.phase1.settings import load_settings, require_api_key

SYSTEM_PROMPT = "You are a concise research assistant. Answer with one sentence."
USER_INPUT = "Explain why checkpointing matters for long-running agents."


def main() -> int:
    """Run the stream example. Returns exit code."""
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

    print("Streaming response (normalized chunks):")
    print("-" * 50)

    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": USER_INPUT}]},
        stream_mode="updates",
    ):
        normalized = normalize_chunk(chunk)
        for nc in normalized:
            print(render_chunk(nc))

    return 0


if __name__ == "__main__":
    sys.exit(main())
