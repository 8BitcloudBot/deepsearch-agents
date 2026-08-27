"""Configuration for the citation semantic adapter acceptance seam."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

PHASE4_REAL_SEMANTIC_SMOKE_ENV = "PHASE4_REAL_SEMANTIC_SMOKE"


@dataclass(frozen=True)
class Phase4Settings:
    real_semantic_smoke: bool = False
    real_semantic_model: str = "openai:gpt-4.1-mini"
    real_semantic_base_url: str | None = None
    real_semantic_api_key: str | None = None
    real_semantic_timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Phase4Settings":
        env = environ if environ is not None else os.environ
        return cls(
            real_semantic_smoke=env.get(PHASE4_REAL_SEMANTIC_SMOKE_ENV, "") == "1",
            real_semantic_model=env.get(
                "PHASE4_REAL_SEMANTIC_MODEL",
                env.get("MODEL_NAME", "openai:gpt-4.1-mini"),
            ),
            real_semantic_base_url=(
                env.get("PHASE4_REAL_SEMANTIC_BASE_URL")
                or env.get("MODEL_BASE_URL")
                or None
            ),
            real_semantic_api_key=(
                env.get("PHASE4_REAL_SEMANTIC_API_KEY")
                or env.get("MODEL_API_KEY")
                or None
            ),
            real_semantic_timeout_seconds=float(
                env.get("PHASE4_REAL_SEMANTIC_TIMEOUT_SECONDS", "30.0")
            ),
        )
