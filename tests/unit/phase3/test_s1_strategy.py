"""Unit: S1 Orchestrator-Workers deterministic strategy (P3-4).

Covers the strategy identity (``s1-orchestrator-workers`` /
``mock:deterministic``, prompt/config fingerprints), the three bounded
worker roles (Web snapshot, catalog, knowledge), the worker-output
contract (``worker_id``, ordered ``source_ids``, ``summary``,
``latency_ms``, ``status``), allowed-source discipline per worker kind,
deterministic fixed-order merge, partial worker failure becoming a
structured limitation without aborting the remaining workers/case,
offline zero cost / unavailable latency, the StrategyOutput contract
matching S0, and additive registry selection (``s1``).
"""

import hashlib
import json
import re

import pytest

from benchmarks.evaluation.contracts import EvaluationCase, StrategyOutput
from benchmarks.evaluation.datasets import load_dataset
from benchmarks.evaluation.source_contracts import Corpus, SourceRecord
from benchmarks.evaluation.source_corpus import load_corpus
from benchmarks.evaluation.strategies import get_strategy
from benchmarks.evaluation.strategies.s1_orchestrator_workers import (
    MODEL_ID,
    PROMPT_ID,
    S1_CONFIG,
    S1_SYSTEM_PROMPT,
    STRATEGY_ID,
    WORKER_ROLES,
    DeterministicWorker,
    S1OrchestratorWorkersStrategy,
    WorkerOutput,
)

_ABS_PATH_RE = re.compile(r"(?:/Users/|/tmp/|/private/)")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _worker(worker_id: str) -> DeterministicWorker:
    return DeterministicWorker(
        worker_id=worker_id,
        kind=worker_id,
        role=worker_id,
        max_source_chars=4000,
    )


class _ExplodingWorker(DeterministicWorker):
    """Worker whose run always raises; exercises the failure boundary."""

    def run(self, sources):
        raise RuntimeError("boom")


@pytest.fixture(scope="module")
def dataset():
    return load_dataset()


@pytest.fixture(scope="module")
def corpus():
    return load_corpus()


def test_strategy_identity_fields():
    strategy = S1OrchestratorWorkersStrategy()
    assert strategy.strategy_id == "s1-orchestrator-workers"
    assert strategy.model_id == "mock:deterministic"
    assert strategy.prompt_id == "s1-orchestrator-workers-v1"
    assert STRATEGY_ID == "s1-orchestrator-workers"
    assert MODEL_ID == "mock:deterministic"
    assert PROMPT_ID == "s1-orchestrator-workers-v1"


def test_prompt_and_config_fingerprints_are_reproducible():
    assert S1OrchestratorWorkersStrategy.prompt_sha256 == _sha256(S1_SYSTEM_PROMPT)
    canonical = json.dumps(
        S1_CONFIG, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    assert S1OrchestratorWorkersStrategy.config_sha256 == _sha256(canonical)


def test_exactly_three_bounded_worker_roles_in_fixed_order():
    strategy = S1OrchestratorWorkersStrategy()
    assert [worker.worker_id for worker in strategy.workers] == [
        "web_snapshot",
        "catalog",
        "knowledge",
    ]
    assert tuple(worker.worker_id for worker in strategy.workers) == WORKER_ROLES
    assert len(strategy.workers) == 3
    assert WORKER_ROLES == ("web_snapshot", "catalog", "knowledge")
    for worker in strategy.workers:
        assert worker.kind == worker.worker_id
        assert worker.max_source_chars > 0


def test_worker_output_contract_fields_and_roundtrip():
    out = WorkerOutput(
        worker_id="catalog",
        source_ids=("catalog-frameworks-v1",),
        summary="## Catalog\ncontent",
        latency_ms=None,
        status="success",
    )
    data = out.to_dict()
    assert data["worker_id"] == "catalog"
    assert data["source_ids"] == ("catalog-frameworks-v1",)
    assert data["summary"].startswith("## Catalog")
    assert data["latency_ms"] is None
    assert data["status"] == "success"
    assert "error_code" in data
    assert "limitations" in data
    assert WorkerOutput.from_dict(data) == out


def test_workers_receive_only_allowed_sources_of_their_own_kind(dataset, corpus):
    # seed-002 allows web + knowledge but NOT catalog.
    case = dataset.cases[1]
    strategy = S1OrchestratorWorkersStrategy()
    outputs = strategy.run_workers(case, corpus)

    assert [out.worker_id for out in outputs] == [
        "web_snapshot",
        "catalog",
        "knowledge",
    ]
    by_id = {out.worker_id: out for out in outputs}
    assert by_id["catalog"].status == "skipped"
    assert by_id["catalog"].source_ids == ()
    assert by_id["catalog"].error_code == "no_sources_of_kind"

    corpus_order = [source.source_id for source in corpus.sources]
    for out in outputs:
        assert all(sid in case.allowed_source_ids for sid in out.source_ids)
        for sid in out.source_ids:
            kind = next(
                source.kind for source in corpus.sources if source.source_id == sid
            )
            assert kind == out.worker_id
        # source_ids are ordered by corpus order.
        assert out.source_ids == tuple(
            sid for sid in corpus_order if sid in out.source_ids
        )
        assert out.latency_ms is None
        assert out.status in {"success", "skipped", "failed"}


def test_run_returns_success_for_seed_case(dataset, corpus):
    case = dataset.cases[0]  # seed-001: all three kinds allowed
    output = S1OrchestratorWorkersStrategy().run(case, corpus)

    assert isinstance(output, StrategyOutput)
    assert output.status == "success"
    assert output.case_id == case.case_id
    assert output.cost_usd == 0.0
    assert output.tool_calls == len(case.allowed_source_ids)
    assert output.source_coverage == 1.0
    assert 0.0 <= output.topic_recall <= 1.0
    assert output.latency_ms is None
    assert output.artifact_paths == ()
    assert output.answer
    assert output.limitations
    # The answer renders the fixed worker boundaries.
    assert "## Worker boundaries" in output.answer
    assert "web_snapshot (Web snapshot): status=success" in output.answer
    assert "catalog (Catalog): status=success" in output.answer
    assert "knowledge (Knowledge): status=success" in output.answer


def test_run_uses_only_allowed_sources(dataset, corpus):
    case = dataset.cases[1]  # seed-002: catalog-frameworks-v1 not allowed
    output = S1OrchestratorWorkersStrategy().run(case, corpus)

    for source_id in case.allowed_source_ids:
        assert source_id in output.answer
    assert "catalog-frameworks-v1" not in output.answer
    assert "catalog (Catalog): status=skipped" in output.answer
    assert output.tool_calls == len(case.allowed_source_ids)
    assert output.source_coverage == 1.0


def test_run_is_deterministic(dataset, corpus):
    case = dataset.cases[2]
    strategy = S1OrchestratorWorkersStrategy()
    first = strategy.run(case, corpus)
    second = strategy.run(case, corpus)
    assert first == second
    assert strategy.run_workers(case, corpus) == strategy.run_workers(case, corpus)


def test_merge_order_is_fixed_worker_order(dataset, corpus):
    strategy = S1OrchestratorWorkersStrategy()
    for case in (dataset.cases[0], dataset.cases[2], dataset.cases[9]):
        outputs = strategy.run_workers(case, corpus)
        assert [out.worker_id for out in outputs] == [
            "web_snapshot",
            "catalog",
            "knowledge",
        ]
        answer = strategy.run(case, corpus).answer
        positions = [answer.index(f"### {wid}") for wid in WORKER_ROLES]
        assert positions == sorted(positions)


def test_partial_worker_failure_becomes_structured_limitation(dataset, corpus):
    """A failing worker is recorded as a structured limitation and the
    remaining workers (and the case) still complete."""
    case = dataset.cases[0]  # all three kinds allowed
    strategy = S1OrchestratorWorkersStrategy(
        workers=(
            _worker("web_snapshot"),
            _ExplodingWorker("catalog", "catalog", "Catalog", 4000),
            _worker("knowledge"),
        )
    )

    output = strategy.run(case, corpus)
    assert output.status == "success"
    assert output.case_id == case.case_id
    # The two healthy workers still produced their sources.
    assert "web-agent-frameworks-v1" in output.answer
    assert "knowledge-evaluation-notes-v1" in output.answer
    assert output.tool_calls == 2
    assert output.source_coverage == round(2 / 3, 4)
    # The failure is a structured limitation, never exception text.
    assert any("worker catalog failed" in lim for lim in output.limitations)
    assert any("redacted" in lim for lim in output.limitations)
    assert "RuntimeError" not in " ".join(output.limitations)
    assert "boom" not in " ".join(output.limitations)

    worker_outputs = strategy.run_workers(case, corpus)
    by_id = {out.worker_id: out for out in worker_outputs}
    assert by_id["catalog"].status == "failed"
    assert by_id["catalog"].error_code == "worker_error"
    assert by_id["web_snapshot"].status == "success"
    assert by_id["knowledge"].status == "success"


def test_all_workers_failed_yields_failed_case(dataset, corpus):
    case = dataset.cases[0]
    strategy = S1OrchestratorWorkersStrategy(
        workers=tuple(_ExplodingWorker(wid, wid, wid, 4000) for wid in WORKER_ROLES)
    )
    output = strategy.run(case, corpus)
    assert output.status == "failed"
    assert output.error_code == "all_workers_failed"
    assert output.case_id == case.case_id
    assert output.latency_ms is None
    assert output.cost_usd == 0.0
    assert any("failed" in lim for lim in output.limitations)


def test_skipped_when_case_has_no_allowed_sources(corpus):
    case = EvaluationCase(
        case_id="seed-999",
        split="seed",
        question="Question with no allowed sources?",
        expected_topics=("single-agent",),
        allowed_source_ids=(),
        difficulty="basic",
    )
    output = S1OrchestratorWorkersStrategy().run(case, corpus)
    assert output.status == "skipped"
    assert output.error_code == "no_allowed_sources"
    assert output.limitations


def test_offline_output_never_claims_real_provider_quality(dataset, corpus):
    output = S1OrchestratorWorkersStrategy().run(dataset.cases[0], corpus)
    answer = output.answer.lower()
    assert "offline" in answer
    assert "deterministic" in answer
    assert "mock:deterministic" in output.answer
    joined = " ".join(output.limitations).lower()
    assert "offline" in joined
    assert not _ABS_PATH_RE.search(output.answer)
    # Offline latency is never measured or fabricated: no latency prose.
    assert "latency" not in answer
    for out in S1OrchestratorWorkersStrategy().run_workers(dataset.cases[0], corpus):
        assert out.latency_ms is None


def test_registry_selects_s1_by_cli_name():
    strategy = get_strategy("s1")
    assert isinstance(strategy, S1OrchestratorWorkersStrategy)
    assert strategy.strategy_id == "s1-orchestrator-workers"
    with pytest.raises(ValueError, match="unknown"):
        get_strategy("nope")


# ---------------------------------------------------------------------------
# P3-4 acceptance rework: fail-closed worker boundary. Every worker return is
# validated inside the per-worker exception boundary; malformed returns become
# one structured failed WorkerOutput (``invalid_worker_output``) that never
# contaminates answer metrics and never aborts the remaining workers or later
# cases. Topology must be exactly the three unique WORKER_ROLES in fixed order
# with matching kind.
# ---------------------------------------------------------------------------


def _sources_for(case, corpus, kind) -> tuple:
    return tuple(
        source
        for source in corpus.sources
        if source.source_id in case.allowed_source_ids and source.kind == kind
    )


def _fixed_worker(worker_id: str, output) -> DeterministicWorker:
    """Worker whose run returns exactly ``output`` without reading sources."""

    class _FixedWorker(DeterministicWorker):
        def run(self, sources):
            return self._output

    worker = _FixedWorker(
        worker_id=worker_id,
        kind=worker_id,
        role=worker_id,
        max_source_chars=4000,
    )
    worker._output = output
    return worker


def _strategy_with_output(worker_id: str, output) -> S1OrchestratorWorkersStrategy:
    """Strategy with one injected fixed-output worker and two healthy ones."""
    return S1OrchestratorWorkersStrategy(
        workers=tuple(
            _fixed_worker(wid, output) if wid == worker_id else _worker(wid)
            for wid in WORKER_ROLES
        )
    )


def _synthetic_web_pair():
    """Synthetic corpus + case with two allowed web_snapshot sources in
    corpus order (alpha, beta) so ordering/subset violations are real."""
    corpus = Corpus(
        corpus_id="synthetic-v1",
        schema_version=1,
        captured_at="2026-08-07",
        sources=(
            SourceRecord(
                source_id="web-alpha-v1",
                kind="web_snapshot",
                title="Alpha",
                origin="https://example.test/a",
                captured_at="2026-08-07",
                content="alpha content",
                content_sha256=_sha256("alpha content"),
            ),
            SourceRecord(
                source_id="web-beta-v1",
                kind="web_snapshot",
                title="Beta",
                origin="https://example.test/b",
                captured_at="2026-08-07",
                content="beta content",
                content_sha256=_sha256("beta content"),
            ),
        ),
    )
    case = EvaluationCase(
        case_id="seed-999",
        split="seed",
        question="Synthetic two-web-source case?",
        expected_topics=("topic",),
        allowed_source_ids=("web-alpha-v1", "web-beta-v1"),
        difficulty="basic",
    )
    return case, corpus


def _assert_invalid_worker_output(output: WorkerOutput, worker_id: str) -> None:
    assert output.status == "failed"
    assert output.error_code == "invalid_worker_output"
    assert output.source_ids == ()
    assert output.summary == ""
    assert output.latency_ms is None
    assert any("invalid worker output" in lim for lim in output.limitations)


def _outputs_by_id(strategy, case, corpus) -> dict[str, WorkerOutput]:
    return {out.worker_id: out for out in strategy.run_workers(case, corpus)}


def test_rejects_unauthorized_source_ids_from_injected_worker(dataset, corpus):
    """The verified RED repro: a success output naming a source that was never
    passed to the worker must be rejected, never leaked into the answer."""
    case = dataset.cases[0]  # seed-001: one allowed source per kind
    leaked = WorkerOutput(
        worker_id="web_snapshot",
        source_ids=("forbidden-source",),
        summary="injected",
        status="success",
    )
    strategy = _strategy_with_output("web_snapshot", leaked)

    outputs = _outputs_by_id(strategy, case, corpus)
    _assert_invalid_worker_output(outputs["web_snapshot"], "web_snapshot")
    assert outputs["catalog"].status == "success"
    assert outputs["knowledge"].status == "success"

    output = strategy.run(case, corpus)
    assert output.status == "success"  # two healthy workers still succeeded
    assert "forbidden-source" not in output.answer
    assert "injected" not in output.answer
    assert output.tool_calls == 2
    assert output.source_coverage == round(2 / 3, 4)
    assert any("invalid worker output" in lim for lim in output.limitations)


def test_rejects_duplicate_source_ids(dataset, corpus):
    case = dataset.cases[0]
    web = _sources_for(case, corpus, "web_snapshot")
    dup = WorkerOutput(
        worker_id="web_snapshot",
        source_ids=(web[0].source_id, web[0].source_id),
        summary="dup",
        status="success",
    )
    outputs = _outputs_by_id(_strategy_with_output("web_snapshot", dup), case, corpus)
    _assert_invalid_worker_output(outputs["web_snapshot"], "web_snapshot")


def test_rejects_out_of_order_source_ids():
    case, corpus = _synthetic_web_pair()
    reordered = WorkerOutput(
        worker_id="web_snapshot",
        source_ids=("web-beta-v1", "web-alpha-v1"),
        summary="reversed",
        status="success",
    )
    outputs = _outputs_by_id(
        _strategy_with_output("web_snapshot", reordered), case, corpus
    )
    _assert_invalid_worker_output(outputs["web_snapshot"], "web_snapshot")


def test_rejects_source_ids_not_exactly_the_passed_set():
    case, corpus = _synthetic_web_pair()
    subset = WorkerOutput(
        worker_id="web_snapshot",
        source_ids=("web-alpha-v1",),
        summary="subset",
        status="success",
    )
    outputs = _outputs_by_id(
        _strategy_with_output("web_snapshot", subset), case, corpus
    )
    _assert_invalid_worker_output(outputs["web_snapshot"], "web_snapshot")


def test_rejects_mismatched_worker_id(dataset, corpus):
    case = dataset.cases[0]
    forged = WorkerOutput(
        worker_id="knowledge",
        source_ids=(),
        summary="",
        status="skipped",
    )
    strategy = _strategy_with_output("web_snapshot", forged)

    outputs = _outputs_by_id(strategy, case, corpus)
    _assert_invalid_worker_output(outputs["web_snapshot"], "web_snapshot")
    # The forged id never replaces the real knowledge worker's output.
    assert outputs["knowledge"].status == "success"


def test_rejects_non_worker_output_return(dataset, corpus):
    case = dataset.cases[0]
    for bad in (None, {"worker_id": "web_snapshot", "status": "success"}):
        outputs = _outputs_by_id(
            _strategy_with_output("web_snapshot", bad), case, corpus
        )
        _assert_invalid_worker_output(outputs["web_snapshot"], "web_snapshot")


def test_rejects_invalid_status(dataset, corpus):
    case = dataset.cases[0]
    bad = WorkerOutput(
        worker_id="web_snapshot",
        source_ids=(),
        summary="",
        status="injected",
    )
    outputs = _outputs_by_id(_strategy_with_output("web_snapshot", bad), case, corpus)
    _assert_invalid_worker_output(outputs["web_snapshot"], "web_snapshot")


def test_rejects_fabricated_latency(dataset, corpus):
    case = dataset.cases[0]
    web = _sources_for(case, corpus, "web_snapshot")
    for latency in (123, 0):
        bad = WorkerOutput(
            worker_id="web_snapshot",
            source_ids=tuple(s.source_id for s in web),
            summary="measured?",
            latency_ms=latency,
            status="success",
        )
        outputs = _outputs_by_id(
            _strategy_with_output("web_snapshot", bad), case, corpus
        )
        _assert_invalid_worker_output(outputs["web_snapshot"], "web_snapshot")


def test_rejects_invalid_field_types(dataset, corpus):
    case = dataset.cases[0]
    web = _sources_for(case, corpus, "web_snapshot")
    web_ids = tuple(s.source_id for s in web)
    bad_outputs = [
        WorkerOutput(
            worker_id="web_snapshot",
            source_ids=web_ids,
            summary=123,
            status="success",
        ),
        WorkerOutput(
            worker_id="web_snapshot",
            source_ids="web-agent-frameworks-v1",  # str, not a tuple
            summary="",
            status="success",
        ),
        WorkerOutput(
            worker_id="web_snapshot",
            source_ids=web_ids,
            summary="",
            status="success",
            limitations=(42,),
        ),
        WorkerOutput(
            worker_id="web_snapshot",
            source_ids=web_ids,
            summary="",
            status="success",
            error_code=5,
        ),
    ]
    for bad in bad_outputs:
        outputs = _outputs_by_id(
            _strategy_with_output("web_snapshot", bad), case, corpus
        )
        _assert_invalid_worker_output(outputs["web_snapshot"], "web_snapshot")


def test_rejects_skipped_or_failed_outputs_claiming_source_ids(dataset, corpus):
    case = dataset.cases[0]
    web = _sources_for(case, corpus, "web_snapshot")
    claimed = (web[0].source_id,)
    for status in ("skipped", "failed"):
        bad = WorkerOutput(
            worker_id="web_snapshot",
            source_ids=claimed,
            summary="",
            status=status,
        )
        outputs = _outputs_by_id(
            _strategy_with_output("web_snapshot", bad), case, corpus
        )
        _assert_invalid_worker_output(outputs["web_snapshot"], "web_snapshot")


def test_rejects_invalid_worker_topology():
    # Not exactly the three unique WORKER_ROLES in fixed order with matching
    # kind: construction must fail closed before any run.
    with pytest.raises(ValueError, match="exactly 3 workers"):
        S1OrchestratorWorkersStrategy(workers=(_worker("web_snapshot"),))
    with pytest.raises(ValueError, match="exactly 3 workers"):
        S1OrchestratorWorkersStrategy(workers=())
    with pytest.raises(ValueError, match="exactly 3 workers"):
        S1OrchestratorWorkersStrategy(
            workers=(
                _worker("web_snapshot"),
                _worker("catalog"),
                _worker("knowledge"),
                _worker("web_snapshot"),
            )
        )
    # Wrong fixed order.
    with pytest.raises(ValueError, match="fixed role order"):
        S1OrchestratorWorkersStrategy(
            workers=(
                _worker("knowledge"),
                _worker("catalog"),
                _worker("web_snapshot"),
            )
        )
    # Duplicate role.
    with pytest.raises(ValueError, match="fixed role order"):
        S1OrchestratorWorkersStrategy(
            workers=(
                _worker("web_snapshot"),
                _worker("web_snapshot"),
                _worker("knowledge"),
            )
        )
    # Kind not matching worker_id.
    with pytest.raises(ValueError, match="kind must match"):
        S1OrchestratorWorkersStrategy(
            workers=(
                _worker("web_snapshot"),
                DeterministicWorker("catalog", "web_snapshot", "Catalog", 4000),
                _worker("knowledge"),
            )
        )


def test_invalid_output_does_not_abort_remaining_workers_or_later_cases(
    dataset, corpus
):
    case0 = dataset.cases[0]
    case1 = dataset.cases[1]
    bad = WorkerOutput(
        worker_id="web_snapshot",
        source_ids=("forbidden-source",),
        summary="injected",
        status="success",
    )
    strategy = _strategy_with_output("web_snapshot", bad)

    first = strategy.run(case0, corpus)
    assert first.status == "success"
    assert "forbidden-source" not in first.answer
    assert any("invalid worker output" in lim for lim in first.limitations)

    # A later case on the same strategy still completes with intact workers.
    second = strategy.run(case1, corpus)
    assert second.status == "success"
    assert "forbidden-source" not in second.answer
    outputs = _outputs_by_id(strategy, case1, corpus)
    assert [out.worker_id for out in outputs.values()] == list(WORKER_ROLES)
    assert outputs["catalog"].status == "skipped"
    assert outputs["knowledge"].status == "success"


def test_valid_injected_worker_output_still_accepted(dataset, corpus):
    """Test injection with exactly three valid roles keeps working: a worker
    return that honours the contract is accepted and merged as before."""
    case = dataset.cases[0]
    web = _sources_for(case, corpus, "web_snapshot")
    valid = WorkerOutput(
        worker_id="web_snapshot",
        source_ids=tuple(s.source_id for s in web),
        summary="injected but valid",
        latency_ms=None,
        status="success",
    )
    strategy = _strategy_with_output("web_snapshot", valid)
    output = strategy.run(case, corpus)
    assert output.status == "success"
    assert output.tool_calls == 3
    assert output.source_coverage == 1.0
    assert "injected but valid" in output.answer
    assert output.latency_ms is None
