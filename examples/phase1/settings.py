"""Phase 1 shared settings.

Uses environment variables with safe defaults. No .env file parsing.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Phase1Settings:
    """Immutable settings for Phase 1 examples."""

    model_name: str
    base_url: str | None
    api_key: str | None
    timeout_seconds: float

    def __post_init__(self):
        if not isinstance(self.timeout_seconds, int | float):
            raise ValueError(
                f"timeout_seconds must be a number, got {self.timeout_seconds!r}"
            )
        if self.timeout_seconds <= 0:
            raise ValueError(
                f"timeout_seconds must be positive, got {self.timeout_seconds}"
            )


def load_settings() -> Phase1Settings:
    """Load settings from environment variables with defaults."""
    timeout_str = os.environ.get("MODEL_TIMEOUT_SECONDS", "60")
    try:
        timeout_seconds = float(timeout_str)
    except (ValueError, TypeError):
        raise ValueError(
            f"MODEL_TIMEOUT_SECONDS must be a number, got {timeout_str!r}"
        ) from None

    return Phase1Settings(
        model_name=os.environ.get("MODEL_NAME", "openai:gpt-4.1-mini"),
        base_url=os.environ.get("MODEL_BASE_URL") or None,
        api_key=os.environ.get("MODEL_API_KEY") or None,
        timeout_seconds=timeout_seconds,
    )


def require_api_key(settings: Phase1Settings) -> str:
    """Return the API key or raise RuntimeError with actionable message.

    The error message MUST NOT contain any key value.
    """
    if not settings.api_key:
        raise RuntimeError(
            "MODEL_API_KEY environment variable is not set. "
            "Set it to your API key before running examples that need a model. "
            "Example: export MODEL_API_KEY=your-key-here"
        )
    return settings.api_key
