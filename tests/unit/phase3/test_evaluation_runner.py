"""Unit: unified evaluation runner (P3-3).

Covers ordered execution, terminal case statuses (success / failed /
skipped with skipped distinct from failed), one-failure isolation,
aggregate counts, the three output files under the caller's directory
only, manifest fingerprint fields, exception-text redaction,
deterministic reruns (identical statuses/metrics/fingerprints except
``run_id``/``started_at``), fail-closed offline invariants (model id,
zero cost), per-case strategy-output validation, truthful unmeasured
latency, versioned-data write protection and git-provenance binding.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

from benchmarks.evaluation.contracts import (
    CaseResult,
    Dataset,
    EvaluationCase,
    StrategyOutput,
)
from benchmarks.evaluation.reporting import write_report
from benchmarks.evaluation.runner import RUNNER_VERSION, EvaluationRunner
from benchmarks.evaluation.source_contracts import Corpus, SourceRecord, corpus_sha256

_FAKE_HASH = "ab" * 32
_ABS_PATH_RE = re.compile(r"(?:/Users/|/tmp/|/private/)")
_DATA_PHASE3 = Path(__file__).resolve().parents[3] / "data" / "phase3"


def _source(source_id: str, kind: str = "web_snapshot") -> SourceRecord:
    return SourceRecord(
        source_id=source_id,
        kind=kind,
        title=f"Title {source_id}",
        origin="unit fixture",
        captured_at="2026-08-07",
        content=f"Content for {source_id}. single-agent orchestrator offline.",
        content_sha256=_FAKE_HASH,
    )


def _corpus() -> Corpus:
    return Corpus(
        corpus_id="unit-corpus-v1",
        schema_version=1,
        captured_at="2026-08-07",
        sources=(_source("web-a-v1"), _source("catalog-b-v1", "catalog")),
    )


def _dataset() -> Dataset:
    cases = tuple(
        EvaluationCase(
            case_id=f"seed-{i:03d}",
            split="seed",
            question=f"Question {i}?",
            expected_topics=("single-agent",),
            allowed_source_ids=("web-a-v1", "catalog-b-v1"),
            difficulty="basic",
        )
        for i in range(1, 11)
    )
    return Dataset(
        dataset_id="unit-seed-v1",
        schema_version=1,
        corpus_id="unit-corpus-v1",
        file="unit-seed.jsonl",
        file_sha256=_FAKE_HASH,
        cases=cases,
    )


class RecordingStrategy:
    """Fake strategy that records invocation order and can fail/skip cases."""

    strategy_id = "unit-recording"
    model_id = "mock:deterministic"
    prompt_id = "unit-prompt-v1"
    prompt_sha256 = _FAKE_HASH
    config_sha256 = _FAKE_HASH

    def __init__(
        self,
        failures: frozenset[str] = frozenset(),
        skips: frozenset[str] = frozenset(),
    ):
        self.calls: list[str] = []
        self._failures = failures
        self._skips = skips

    def run(self, case: EvaluationCase, corpus: Corpus) -> StrategyOutput:
        self.calls.append(case.case_id)
        if case.case_id in self._failures:
            raise ValueError(f"boom for {case.case_id}: /tmp/secret/{case.case_id}")
        if case.case_id in self._skips:
            return StrategyOutput(
                case_id=case.case_id,
                status="skipped",
                answer="",
                error_code="skipped",
                limitations=("skipped by unit fixture",),
            )
        return StrategyOutput(
            case_id=case.case_id,
            status="success",
            answer=f"answer-{case.case_id}",
            cost_usd=0.0,
            tool_calls=2,
            topic_recall=0.5,
            source_coverage=1.0,
            limitations=("unit fixture",),
        )


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _manifest_dict(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_run_returns_results_in_stable_dataset_order():
    strategy = RecordingStrategy()
    report = EvaluationRunner(strategy).run(_dataset(), _corpus())

    assert [case.case_id for case in report.cases] == [
        f"seed-{i:03d}" for i in range(1, 11)
    ]
    assert strategy.calls == [case.case_id for case in report.cases]


def test_one_failure_does_not_abort_later_cases():
    strategy = RecordingStrategy(failures=frozenset({"seed-003"}))
    report = EvaluationRunner(strategy).run(_dataset(), _corpus())

    assert len(report.cases) == 10
    assert len(strategy.calls) == 10
    assert report.cases[2].status == "failed"
    assert report.cases[2].error_code == "strategy_error"
    assert [case.status for case in report.cases[:2]] == ["success", "success"]
    assert [case.status for case in report.cases[3:]] == ["success"] * 7


def test_skipped_is_distinct_from_failed():
    strategy = RecordingStrategy(
        failures=frozenset({"seed-004"}), skips=frozenset({"seed-003"})
    )
    report = EvaluationRunner(strategy).run(_dataset(), _corpus())

    statuses = [case.status for case in report.cases]
    assert statuses.count("success") == 8
    assert statuses.count("skipped") == 1
    assert statuses.count("failed") == 1
    assert report.cases[2].status == "skipped"
    assert report.cases[2].error_code == "skipped"
    assert report.cases[3].status == "failed"
    assert report.aggregate.success == 8
    assert report.aggregate.skipped == 1
    assert report.aggregate.failed == 1
    assert report.aggregate.total == 10


def test_aggregate_counts_and_rates():
    strategy = RecordingStrategy(
        failures=frozenset({"seed-004"}), skips=frozenset({"seed-003"})
    )
    report = EvaluationRunner(strategy).run(_dataset(), _corpus())

    assert report.aggregate.total == 10
    assert report.aggregate.success == 8
    assert report.aggregate.failed == 1
    assert report.aggregate.skipped == 1
    assert report.aggregate.success_rate == pytest.approx(0.8)
    # The failed and skipped rows carry no measured cost (None), so the
    # aggregate total is unknown — never a fabricated 0.0 over partial data.
    assert report.aggregate.cost_total_usd is None
    # No strategy reported latency, so aggregates must be unavailable
    # (None), never fabricated 0 milliseconds.
    assert report.aggregate.latency_mean_ms is None
    assert report.aggregate.latency_median_ms is None
    assert report.aggregate.latency_max_ms is None


def test_reported_latency_is_aggregated_when_present():
    class LatencyStrategy(RecordingStrategy):
        def run(self, case, corpus):
            output = super().run(case, corpus)
            return StrategyOutput(
                case_id=output.case_id,
                status=output.status,
                answer=output.answer,
                artifact_paths=output.artifact_paths,
                latency_ms=10 + int(case.case_id[-3:]) % 3 * 5,
                cost_usd=output.cost_usd,
                tool_calls=output.tool_calls,
                topic_recall=output.topic_recall,
                source_coverage=output.source_coverage,
                error_code=output.error_code,
                limitations=output.limitations,
            )

    report = EvaluationRunner(LatencyStrategy()).run(_dataset(), _corpus())
    # latencies are 10 / 15 / 20 repeating across the 10 cases
    assert report.aggregate.latency_mean_ms == pytest.approx(15.0)
    assert report.aggregate.latency_median_ms == pytest.approx(15.0)
    assert report.aggregate.latency_max_ms == 20


def test_output_files_written_under_caller_directory_only(tmp_path: Path):
    EvaluationRunner(RecordingStrategy()).run(
        _dataset(), _corpus(), output_dir=tmp_path
    )

    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "cases.jsonl",
        "manifest.json",
        "summary.md",
    ]
    manifest = _manifest_dict(tmp_path / "manifest.json")
    assert manifest["run_id"]
    assert manifest["started_at"]
    assert manifest["runner_version"] == RUNNER_VERSION
    assert manifest["execution_mode"] == "offline"
    assert manifest["strategy_id"] == "unit-recording"
    assert manifest["dataset_id"] == "unit-seed-v1"
    assert manifest["dataset_sha256"] == _FAKE_HASH
    assert manifest["corpus_id"] == "unit-corpus-v1"
    assert manifest["corpus_sha256"] == corpus_sha256(_corpus())
    assert manifest["model_id"] == "mock:deterministic"
    assert manifest["prompt_id"] == "unit-prompt-v1"
    assert manifest["prompt_sha256"] == _FAKE_HASH
    assert manifest["config_sha256"] == _FAKE_HASH
    assert re.fullmatch(r"[0-9a-f]{40}", manifest["git_commit"])
    assert len(_read_jsonl(tmp_path / "cases.jsonl")) == 10
    assert (tmp_path / "summary.md").read_text(encoding="utf-8")


def test_manifest_git_commit_matches_head():
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    runner = EvaluationRunner(RecordingStrategy())
    report = runner.run(_dataset(), _corpus())
    assert report.manifest.git_commit == head


def test_case_result_fields_are_complete_and_offline(tmp_path: Path):
    EvaluationRunner(RecordingStrategy()).run(
        _dataset(), _corpus(), output_dir=tmp_path
    )
    for row in _read_jsonl(tmp_path / "cases.jsonl"):
        assert set(row) == {
            "case_id",
            "status",
            "answer",
            "artifact_paths",
            "latency_ms",
            "cost_usd",
            "tool_calls",
            "topic_recall",
            "source_coverage",
            "error_code",
            "limitations",
        }
        assert row["status"] in {"success", "failed", "skipped"}
        assert row["latency_ms"] is None
        assert row["cost_usd"] == 0.0
        assert isinstance(row["tool_calls"], int)
        assert 0.0 <= row["topic_recall"] <= 1.0
        assert 0.0 <= row["source_coverage"] <= 1.0
        assert isinstance(row["artifact_paths"], list)
        assert isinstance(row["limitations"], list)


def test_exception_text_is_redacted(tmp_path: Path):
    EvaluationRunner(RecordingStrategy(failures=frozenset({"seed-003"}))).run(
        _dataset(), _corpus(), output_dir=tmp_path
    )
    for name in ("manifest.json", "cases.jsonl", "summary.md"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert "boom" not in text
        assert "secret" not in text
    row = _read_jsonl(tmp_path / "cases.jsonl")[2]
    assert row["status"] == "failed"
    assert row["error_code"] == "strategy_error"
    assert row["answer"] == ""


def test_no_absolute_output_paths(tmp_path: Path):
    EvaluationRunner(RecordingStrategy()).run(
        _dataset(), _corpus(), output_dir=tmp_path
    )
    for name in ("manifest.json", "cases.jsonl", "summary.md"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert str(tmp_path) not in text
        assert not _ABS_PATH_RE.search(text)


def test_invalid_strategy_status_is_coerced_to_failed():
    class BadStatusStrategy(RecordingStrategy):
        def run(self, case, corpus):
            return StrategyOutput(case_id=case.case_id, status="running", answer="x")

    report = EvaluationRunner(BadStatusStrategy()).run(_dataset(), _corpus())
    assert report.cases[0].status == "failed"
    assert report.cases[0].error_code == "invalid_status"


def test_live_execution_mode_is_rejected():
    with pytest.raises(ValueError, match="offline"):
        EvaluationRunner(RecordingStrategy(), execution_mode="live")


def test_deterministic_reruns_identical_except_run_id_and_started_at(
    tmp_path: Path,
):
    dataset, corpus = _dataset(), _corpus()
    first_dir, second_dir = tmp_path / "a", tmp_path / "b"

    EvaluationRunner(RecordingStrategy()).run(dataset, corpus, output_dir=first_dir)
    EvaluationRunner(RecordingStrategy()).run(dataset, corpus, output_dir=second_dir)

    first_cases = (first_dir / "cases.jsonl").read_bytes()
    second_cases = (second_dir / "cases.jsonl").read_bytes()
    assert first_cases == second_cases

    first_manifest = _manifest_dict(first_dir / "manifest.json")
    second_manifest = _manifest_dict(second_dir / "manifest.json")
    first_run_id = first_manifest.pop("run_id")
    second_run_id = second_manifest.pop("run_id")
    first_started = first_manifest.pop("started_at")
    second_started = second_manifest.pop("started_at")
    assert first_run_id != second_run_id
    # Timestamps may legitimately differ between runs; each summary is
    # normalized independently against its own run_id/started_at.
    assert first_manifest == second_manifest

    first_summary = (first_dir / "summary.md").read_text(encoding="utf-8")
    second_summary = (second_dir / "summary.md").read_text(encoding="utf-8")
    first_summary = first_summary.replace(first_run_id, "X").replace(first_started, "X")
    second_summary = second_summary.replace(second_run_id, "X").replace(
        second_started, "X"
    )
    assert first_summary == second_summary


def test_report_carries_terminal_case_results_and_limitations():
    strategy = RecordingStrategy(skips=frozenset({"seed-003"}))
    report = EvaluationRunner(strategy).run(_dataset(), _corpus())

    assert isinstance(report.cases, tuple)
    assert all(isinstance(case, CaseResult) for case in report.cases)
    assert report.skipped_reasons
    assert report.limitations


# ---------------------------------------------------------------------------
# Fail-closed offline invariants
# ---------------------------------------------------------------------------


def test_offline_runner_rejects_other_model_ids():
    with pytest.raises(ValueError, match="mock:deterministic"):
        EvaluationRunner(RecordingStrategy(), model_id="gpt-4")

    class PaidStrategy(RecordingStrategy):
        model_id = "anthropic/claude"

    with pytest.raises(ValueError, match="mock:deterministic"):
        EvaluationRunner(PaidStrategy())


@pytest.mark.parametrize(
    "bad_cost",
    [0.5, -1.0, float("nan"), float("inf"), float("-inf"), True],
    ids=["positive", "negative", "nan", "inf", "neg-inf", "bool"],
)
def test_nonzero_or_nonfinite_cost_is_invalid_strategy_output(bad_cost):
    class CostStrategy(RecordingStrategy):
        def run(self, case, corpus):
            output = super().run(case, corpus)
            if case.case_id == "seed-002":
                return StrategyOutput(
                    case_id=case.case_id,
                    status="success",
                    answer="x",
                    cost_usd=bad_cost,
                )
            return output

    report = EvaluationRunner(CostStrategy()).run(_dataset(), _corpus())
    assert len(report.cases) == 10
    failed = report.cases[1]
    assert failed.case_id == "seed-002"
    assert failed.status == "failed"
    assert failed.error_code == "invalid_strategy_output"
    # Later cases are unaffected: one bad return never aborts the run.
    assert [case.status for case in report.cases[2:]] == ["success"] * 8


def test_skipped_output_with_nonzero_cost_is_invalid():
    class SkippedCostStrategy(RecordingStrategy):
        def run(self, case, corpus):
            output = super().run(case, corpus)
            if case.case_id == "seed-002":
                return StrategyOutput(
                    case_id=case.case_id,
                    status="skipped",
                    answer="",
                    cost_usd=0.01,
                )
            return output

    report = EvaluationRunner(SkippedCostStrategy()).run(_dataset(), _corpus())
    assert report.cases[1].status == "failed"
    assert report.cases[1].error_code == "invalid_strategy_output"
    assert report.cases[2].status == "success"


@pytest.mark.parametrize(
    "output",
    [
        "not-an-output",
        {"case_id": "seed-001", "status": "success", "answer": "x"},
        None,
    ],
    ids=["string", "dict", "none"],
)
def test_non_strategy_output_is_invalid(output):
    class WeirdStrategy(RecordingStrategy):
        def run(self, case, corpus):
            if case.case_id == "seed-002":
                return output
            return super().run(case, corpus)

    report = EvaluationRunner(WeirdStrategy()).run(_dataset(), _corpus())
    assert report.cases[1].status == "failed"
    assert report.cases[1].case_id == "seed-002"
    assert report.cases[1].error_code == "invalid_strategy_output"
    assert report.cases[2].status == "success"


def test_wrong_or_duplicate_case_id_is_invalid():
    class WrongIdStrategy(RecordingStrategy):
        def run(self, case, corpus):
            output = super().run(case, corpus)
            if case.case_id == "seed-003":
                return StrategyOutput(
                    case_id="seed-001",  # duplicate of an earlier case
                    status="success",
                    answer="x",
                )
            if case.case_id == "seed-004":
                return StrategyOutput(
                    case_id="seed-999",  # id not in this dataset
                    status="success",
                    answer="x",
                )
            return output

    report = EvaluationRunner(WrongIdStrategy()).run(_dataset(), _corpus())
    assert report.cases[2].status == "failed"
    assert report.cases[2].case_id == "seed-003"  # input id, not the bogus one
    assert report.cases[2].error_code == "invalid_strategy_output"
    assert report.cases[3].status == "failed"
    assert report.cases[3].case_id == "seed-004"
    assert report.cases[3].error_code == "invalid_strategy_output"
    assert report.cases[4].status == "success"


@pytest.mark.parametrize(
    "paths",
    [
        ("/etc/passwd",),
        ("artifacts/../../escape.txt",),
        ("C:\\evil\\file.txt",),
        ("artifacts/", ""),
        ("artifacts/", 42),
        "not-a-sequence",
    ],
    ids=["absolute", "traversal", "windows-absolute", "empty", "non-str", "non-seq"],
)
def test_unsafe_artifact_paths_are_invalid(paths):
    class PathStrategy(RecordingStrategy):
        def run(self, case, corpus):
            output = super().run(case, corpus)
            if case.case_id == "seed-002":
                return StrategyOutput(
                    case_id=case.case_id,
                    status="success",
                    answer="x",
                    artifact_paths=paths,
                )
            return output

    report = EvaluationRunner(PathStrategy()).run(_dataset(), _corpus())
    assert report.cases[1].status == "failed"
    assert report.cases[1].error_code == "invalid_strategy_output"
    assert report.cases[2].status == "success"


@pytest.mark.parametrize(
    "bad",
    [
        {"latency_ms": 10.5},
        {"latency_ms": -1},
        {"latency_ms": True},
        {"tool_calls": -1},
        {"tool_calls": 2.5},
        {"topic_recall": 1.5},
        {"topic_recall": float("nan")},
        {"source_coverage": -0.1},
        {"source_coverage": float("inf")},
        {"error_code": 42},
        {"error_code": ""},
        {"limitations": "not-a-tuple"},
        {"limitations": ("ok", 42)},
    ],
    ids=[
        "latency-float",
        "latency-negative",
        "latency-bool",
        "tool-calls-negative",
        "tool-calls-float",
        "recall-too-high",
        "recall-nan",
        "coverage-negative",
        "coverage-inf",
        "error-code-int",
        "error-code-empty",
        "limitations-str",
        "limitations-non-str",
    ],
)
def test_bad_field_types_and_ranges_are_invalid(bad):
    class BadFieldStrategy(RecordingStrategy):
        def run(self, case, corpus):
            output = super().run(case, corpus)
            if case.case_id == "seed-005":
                return StrategyOutput(
                    case_id=case.case_id,
                    status="success",
                    answer="x",
                    **bad,
                )
            return output

    report = EvaluationRunner(BadFieldStrategy()).run(_dataset(), _corpus())
    assert report.cases[4].status == "failed"
    assert report.cases[4].case_id == "seed-005"
    assert report.cases[4].error_code == "invalid_strategy_output"
    assert report.cases[5].status == "success"


def test_invalid_output_does_not_leak_bad_value_in_report(tmp_path: Path):
    class LeakyStrategy(RecordingStrategy):
        def run(self, case, corpus):
            if case.case_id == "seed-002":
                return StrategyOutput(
                    case_id="other",
                    status="success",
                    answer="secret-token-abcdef",
                )
            return super().run(case, corpus)

    EvaluationRunner(LeakyStrategy()).run(_dataset(), _corpus(), output_dir=tmp_path)
    for name in ("manifest.json", "cases.jsonl", "summary.md"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert "secret-token-abcdef" not in text


# ---------------------------------------------------------------------------
# Versioned-data write protection
# ---------------------------------------------------------------------------


def test_runner_rejects_output_dir_equal_to_data_phase3():
    with pytest.raises(ValueError, match="data/phase3"):
        EvaluationRunner(RecordingStrategy()).run(
            _dataset(), _corpus(), output_dir=_DATA_PHASE3
        )


def test_runner_rejects_output_dir_inside_data_phase3():
    with pytest.raises(ValueError, match="data/phase3"):
        EvaluationRunner(RecordingStrategy()).run(
            _dataset(), _corpus(), output_dir=_DATA_PHASE3 / "datasets"
        )


def test_write_report_rejects_symlink_alias_to_data_phase3(tmp_path: Path):
    manifest_path = _DATA_PHASE3 / "datasets" / "manifest.json"
    before = manifest_path.read_bytes()
    alias = tmp_path / "data-phase3-alias"
    alias.symlink_to(_DATA_PHASE3, target_is_directory=True)

    report = EvaluationRunner(RecordingStrategy()).run(_dataset(), _corpus())
    with pytest.raises(ValueError, match="data/phase3"):
        write_report(alias, report)

    assert manifest_path.read_bytes() == before
    # No report files may have been written into the versioned data root.
    for name in ("manifest.json", "cases.jsonl", "summary.md"):
        assert not (_DATA_PHASE3 / name).exists()


# ---------------------------------------------------------------------------
# Git provenance
# ---------------------------------------------------------------------------


def test_git_commit_override_must_be_valid_hex():
    with pytest.raises(ValueError, match="40 hex"):
        EvaluationRunner(RecordingStrategy(), git_commit="not-a-commit")


def test_summary_renders_latency_unavailable_not_zero(tmp_path: Path):
    EvaluationRunner(RecordingStrategy()).run(
        _dataset(), _corpus(), output_dir=tmp_path
    )
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "| latency_mean_ms | n/a |" in summary
    assert "| latency_median_ms | n/a |" in summary
    assert "| latency_max_ms | n/a |" in summary
    for line in summary.splitlines():
        if line.startswith("| seed-") and "| success |" in line:
            assert "| n/a |" in line


def test_manifest_fields_never_leak_secrets_or_absolute_paths(tmp_path: Path):
    class EvilStrategy(RecordingStrategy):
        strategy_id = "/Users/evil/strategy"
        model_id = "mock:deterministic"
        prompt_id = "sk-1234567890abcdef"
        prompt_sha256 = "/etc/passwd"
        config_sha256 = "Bearer abcdef123456"
        error_code = "sk-abcdefghijklmnop"

        def run(self, case, corpus):
            output = super().run(case, corpus)
            return StrategyOutput(
                case_id=output.case_id,
                status=output.status,
                answer="answer with sk-0987654321secret",
                error_code=self.error_code,
                limitations=("uses /Users/evil/limitation",),
            )

    EvaluationRunner(EvilStrategy()).run(_dataset(), _corpus(), output_dir=tmp_path)
    for name in ("manifest.json", "cases.jsonl", "summary.md"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert "/Users/" not in text
        assert "sk-" not in text
        assert "Bearer" not in text
        assert "/etc/" not in text
