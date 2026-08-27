"""Unit: S0 Single Agent deterministic strategy (P3-3).

Covers the strategy identity (``s0-single-agent`` /
``mock:deterministic``, prompt/config fingerprints), the
``EvaluationStrategy.run(case, corpus) -> StrategyOutput`` contract on
the real seed-10 cases and corpus, allowed-source discipline,
determinism, zero offline cost, unmeasured latency and the strategy
registry (no S1 yet).
"""

import hashlib
import json
import re

import pytest

from benchmarks.evaluation.contracts import EvaluationCase, StrategyOutput
from benchmarks.evaluation.datasets import load_dataset
from benchmarks.evaluation.source_corpus import load_corpus
from benchmarks.evaluation.strategies import get_strategy
from benchmarks.evaluation.strategies.s0_single_agent import (
    MODEL_ID,
    PROMPT_ID,
    S0_CONFIG,
    S0_SYSTEM_PROMPT,
    STRATEGY_ID,
    S0SingleAgentStrategy,
)

_ABS_PATH_RE = re.compile(r"(?:/Users/|/tmp/|/private/)")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.fixture(scope="module")
def dataset():
    return load_dataset()


@pytest.fixture(scope="module")
def corpus():
    return load_corpus()


def test_strategy_identity_fields():
    strategy = S0SingleAgentStrategy()
    assert strategy.strategy_id == "s0-single-agent"
    assert strategy.model_id == "mock:deterministic"
    assert strategy.prompt_id == "s0-single-agent-v1"
    assert STRATEGY_ID == "s0-single-agent"
    assert MODEL_ID == "mock:deterministic"
    assert PROMPT_ID == "s0-single-agent-v1"


def test_prompt_and_config_fingerprints_are_reproducible():
    assert S0SingleAgentStrategy.prompt_sha256 == _sha256(S0_SYSTEM_PROMPT)
    canonical = json.dumps(
        S0_CONFIG, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    assert S0SingleAgentStrategy.config_sha256 == _sha256(canonical)


def test_run_returns_success_for_seed_case(dataset, corpus):
    case = dataset.cases[0]
    strategy = S0SingleAgentStrategy()
    output = strategy.run(case, corpus)

    assert isinstance(output, StrategyOutput)
    assert output.status == "success"
    assert output.case_id == case.case_id
    assert output.cost_usd == 0.0
    assert output.tool_calls == len(case.allowed_source_ids)
    assert output.source_coverage == 1.0
    assert 0.0 <= output.topic_recall <= 1.0
    # Offline latency is never measured or fabricated.
    assert output.latency_ms is None
    assert output.artifact_paths == ()
    assert output.answer
    assert output.limitations


def test_run_uses_only_allowed_sources(dataset, corpus):
    case = dataset.cases[1]  # seed-002: catalog-frameworks-v1 not allowed
    output = S0SingleAgentStrategy().run(case, corpus)

    for source_id in case.allowed_source_ids:
        assert source_id in output.answer
    assert "catalog-frameworks-v1" not in output.answer
    # tool calls equal the number of allowed sources actually read
    assert output.tool_calls == len(case.allowed_source_ids)


def test_run_is_deterministic(dataset, corpus):
    case = dataset.cases[2]
    strategy = S0SingleAgentStrategy()
    first = strategy.run(case, corpus)
    second = strategy.run(case, corpus)
    assert first == second


def test_offline_output_never_claims_real_provider_quality(dataset, corpus):
    output = S0SingleAgentStrategy().run(dataset.cases[0], corpus)
    answer = output.answer.lower()
    assert "offline" in answer
    assert "deterministic" in answer
    assert "mock:deterministic" in output.answer
    joined = " ".join(output.limitations).lower()
    assert "offline" in joined
    assert not _ABS_PATH_RE.search(output.answer)


def test_all_seed_cases_are_terminal_and_succeed(dataset, corpus):
    strategy = S0SingleAgentStrategy()
    for case in dataset.cases:
        output = strategy.run(case, corpus)
        assert output.status == "success"
        assert output.case_id == case.case_id
        assert output.tool_calls == len(case.allowed_source_ids)
        assert output.source_coverage == 1.0
        assert output.cost_usd == 0.0
        assert output.latency_ms is None


def test_offline_latency_is_never_fabricated(dataset, corpus):
    strategy = S0SingleAgentStrategy()
    for case in dataset.cases:
        output = strategy.run(case, corpus)
        assert output.latency_ms is None
        assert "latency" not in output.answer.lower()


def test_skipped_when_case_has_no_allowed_sources(corpus):
    case = EvaluationCase(
        case_id="seed-999",
        split="seed",
        question="Question with no allowed sources?",
        expected_topics=("single-agent",),
        allowed_source_ids=(),
        difficulty="basic",
    )
    output = S0SingleAgentStrategy().run(case, corpus)
    assert output.status == "skipped"
    assert output.error_code == "no_allowed_sources"
    assert output.limitations


def test_strategy_registry_has_s0_only():
    strategy = get_strategy("s0")
    assert isinstance(strategy, S0SingleAgentStrategy)
    with pytest.raises(ValueError, match="s1"):
        get_strategy("s1-orchestrator-workers")
    with pytest.raises(ValueError, match="unknown"):
        get_strategy("nope")
