"""Evaluation strategy registry (P3-3 S0; P3-4 adds S1).

Strategies implement ``run(case, corpus) -> StrategyOutput`` plus the
identity attributes consumed by the runner manifest: ``strategy_id``,
``model_id``, ``prompt_id``, ``prompt_sha256`` and ``config_sha256``.
CLI names are ``s0`` and ``s1``; the strategy IDs recorded in reports
are ``s0-single-agent`` and ``s1-orchestrator-workers``.
"""

from benchmarks.evaluation.strategies.s0_single_agent import (
    MODEL_ID as S0_MODEL_ID,
)
from benchmarks.evaluation.strategies.s0_single_agent import (
    PROMPT_ID as S0_PROMPT_ID,
)
from benchmarks.evaluation.strategies.s0_single_agent import (
    S0_CONFIG,
    S0_SYSTEM_PROMPT,
    S0SingleAgentStrategy,
)
from benchmarks.evaluation.strategies.s0_single_agent import (
    STRATEGY_ID as S0_STRATEGY_ID,
)
from benchmarks.evaluation.strategies.s1_orchestrator_workers import (
    MODEL_ID as S1_MODEL_ID,
)
from benchmarks.evaluation.strategies.s1_orchestrator_workers import (
    PROMPT_ID as S1_PROMPT_ID,
)
from benchmarks.evaluation.strategies.s1_orchestrator_workers import (
    S1_CONFIG,
    S1_SYSTEM_PROMPT,
    S1OrchestratorWorkersStrategy,
)
from benchmarks.evaluation.strategies.s1_orchestrator_workers import (
    STRATEGY_ID as S1_STRATEGY_ID,
)

STRATEGIES: dict[str, type] = {
    "s0": S0SingleAgentStrategy,
    "s1": S1OrchestratorWorkersStrategy,
}


def get_strategy(name: str):
    """Instantiate a strategy by CLI name (``s0``/``s1``); unknown names raise."""
    try:
        strategy_type = STRATEGIES[name]
    except KeyError as exc:
        known = ", ".join(sorted(STRATEGIES)) or "none"
        raise ValueError(f"unknown strategy {name!r} (known: {known})") from exc
    return strategy_type()


__all__ = [
    "S0_CONFIG",
    "S0_MODEL_ID",
    "S0_PROMPT_ID",
    "S0_SYSTEM_PROMPT",
    "S0SingleAgentStrategy",
    "S0_STRATEGY_ID",
    "S1_CONFIG",
    "S1_MODEL_ID",
    "S1_PROMPT_ID",
    "S1_SYSTEM_PROMPT",
    "S1OrchestratorWorkersStrategy",
    "S1_STRATEGY_ID",
    "STRATEGIES",
    "get_strategy",
]
