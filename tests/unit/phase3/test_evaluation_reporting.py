"""Unit: report manifests and truthful cost rendering (P3-6).

Covers the auditable-fingerprint contract on top of P3-3/P3-4/P3-5:
every manifest carries ``git_dirty`` plus deterministic
``run_fingerprint``/``input_fingerprint`` values (both excluding the
volatile ``run_id``/``started_at``), the input fingerprint binds exactly
dataset/corpus/strategy/model/prompt/config/commit/execution-mode and
the dirty marker, unknown cost is JSON ``null`` and Markdown ``n/a``
(never a fabricated ``0.0``), and new fields are redaction-covered.
"""

import json
import re
from pathlib import Path

from benchmarks.evaluation.contracts import (
    CaseResult,
    Dataset,
    EvaluationCase,
    StrategyOutput,
)
from benchmarks.evaluation.fingerprint import fingerprint
from benchmarks.evaluation.runner import (
    EvaluationRunner,
    _aggregate,
    git_worktree_dirty,
)
from benchmarks.evaluation.source_contracts import Corpus, SourceRecord, corpus_sha256

_FAKE_HASH = "ab" * 32
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")

_INPUT_FINGERPRINT_FIELDS = (
    "dataset_id",
    "dataset_sha256",
    "corpus_id",
    "corpus_sha256",
    "strategy_id",
    "model_id",
    "prompt_id",
    "prompt_sha256",
    "config_sha256",
    "git_commit",
    "execution_mode",
    "git_dirty",
)


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
    """Fake strategy matching the runner manifest identity contract."""

    strategy_id = "unit-recording"
    model_id = "mock:deterministic"
    prompt_id = "unit-prompt-v1"
    prompt_sha256 = _FAKE_HASH
    config_sha256 = _FAKE_HASH

    def run(self, case: EvaluationCase, corpus: Corpus) -> StrategyOutput:
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


def _input_payload(manifest: dict) -> dict:
    return {field: manifest[field] for field in _INPUT_FINGERPRINT_FIELDS}


# ---------------------------------------------------------------------------
# Mandatory manifest fingerprint fields
# ---------------------------------------------------------------------------


def test_manifest_has_all_mandatory_fingerprint_fields(tmp_path: Path):
    EvaluationRunner(RecordingStrategy()).run(
        _dataset(), _corpus(), output_dir=tmp_path
    )
    manifest = _manifest_dict(tmp_path / "manifest.json")

    assert isinstance(manifest["git_dirty"], bool)
    assert _SHA256_HEX_RE.fullmatch(manifest["run_fingerprint"])
    assert _SHA256_HEX_RE.fullmatch(manifest["input_fingerprint"])
    # The dirty marker is a boolean, never a porcelain listing of file paths.
    assert not isinstance(manifest["git_dirty"], str)


def test_input_fingerprint_binds_exactly_the_mandatory_fields():
    report = EvaluationRunner(RecordingStrategy()).run(_dataset(), _corpus())
    manifest = report.manifest.to_dict()

    assert _input_payload(manifest) == {
        "dataset_id": "unit-seed-v1",
        "dataset_sha256": _FAKE_HASH,
        "corpus_id": "unit-corpus-v1",
        "corpus_sha256": corpus_sha256(_corpus()),
        "strategy_id": "unit-recording",
        "model_id": "mock:deterministic",
        "prompt_id": "unit-prompt-v1",
        "prompt_sha256": _FAKE_HASH,
        "config_sha256": _FAKE_HASH,
        "git_commit": manifest["git_commit"],
        "execution_mode": "offline",
        "git_dirty": manifest["git_dirty"],
    }
    assert report.manifest.input_fingerprint == fingerprint(_input_payload(manifest))


def test_run_fingerprint_hashes_all_other_manifest_fields():
    report = EvaluationRunner(RecordingStrategy()).run(_dataset(), _corpus())
    payload = dict(report.manifest.to_dict())
    for volatile in ("run_id", "started_at", "run_fingerprint", "input_fingerprint"):
        payload.pop(volatile)

    assert report.manifest.run_fingerprint == fingerprint(payload)


def test_run_and_input_fingerprints_are_distinct():
    report = EvaluationRunner(RecordingStrategy()).run(_dataset(), _corpus())
    assert report.manifest.run_fingerprint != report.manifest.input_fingerprint


def test_fingerprints_exclude_volatile_run_id_and_started_at(tmp_path: Path):
    first_dir, second_dir = tmp_path / "a", tmp_path / "b"
    EvaluationRunner(RecordingStrategy()).run(
        _dataset(), _corpus(), output_dir=first_dir
    )
    EvaluationRunner(RecordingStrategy()).run(
        _dataset(), _corpus(), output_dir=second_dir
    )

    first = _manifest_dict(first_dir / "manifest.json")
    second = _manifest_dict(second_dir / "manifest.json")
    assert first["run_id"] != second["run_id"]
    assert first["run_fingerprint"] == second["run_fingerprint"]
    assert first["input_fingerprint"] == second["input_fingerprint"]
    # Deterministic reruns share the same input binding and run identity.
    assert _input_payload(first) == _input_payload(second)


def test_input_fingerprint_changes_when_any_bound_input_changes():
    report = EvaluationRunner(RecordingStrategy()).run(_dataset(), _corpus())
    base = _input_payload(report.manifest.to_dict())

    assert fingerprint({**base, "git_dirty": not base["git_dirty"]}) != fingerprint(
        base
    )
    assert fingerprint({**base, "dataset_sha256": "cd" * 32}) != fingerprint(base)
    assert fingerprint(
        {**base, "strategy_id": "s1-orchestrator-workers"}
    ) != fingerprint(base)


def test_git_dirty_marker_matches_the_worktree():
    report = EvaluationRunner(RecordingStrategy()).run(_dataset(), _corpus())
    assert report.manifest.git_dirty is git_worktree_dirty()


def test_summary_renders_the_new_manifest_fingerprint_fields(tmp_path: Path):
    EvaluationRunner(RecordingStrategy()).run(
        _dataset(), _corpus(), output_dir=tmp_path
    )
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    manifest = _manifest_dict(tmp_path / "manifest.json")

    assert "- **git_dirty:**" in summary
    assert manifest["run_fingerprint"] in summary
    assert manifest["input_fingerprint"] in summary


# ---------------------------------------------------------------------------
# Truthful unknown cost: JSON null, Markdown n/a, never a fabricated 0.0
# ---------------------------------------------------------------------------


class UnknownCostStrategy(RecordingStrategy):
    """Success rows whose cost was not measured (unknown, not zero)."""

    def run(self, case, corpus):
        output = super().run(case, corpus)
        return StrategyOutput(
            case_id=output.case_id,
            status=output.status,
            answer=output.answer,
            latency_ms=None,
            cost_usd=None,
            tool_calls=output.tool_calls,
            topic_recall=output.topic_recall,
            source_coverage=output.source_coverage,
            limitations=output.limitations,
        )


def test_unknown_cost_is_json_null_and_markdown_n_a(tmp_path: Path):
    EvaluationRunner(UnknownCostStrategy()).run(
        _dataset(), _corpus(), output_dir=tmp_path
    )

    rows = _read_jsonl(tmp_path / "cases.jsonl")
    assert all(row["cost_usd"] is None for row in rows)
    assert all(row["latency_ms"] is None for row in rows)

    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "| cost_total_usd | n/a |" in summary
    for line in summary.splitlines():
        if line.startswith("| seed-") and "| success |" in line:
            assert "| n/a |" in line

    # Unknown cost must never be invented as 0.0 in either rendering.
    assert "| cost_total_usd | 0.0 |" not in summary


def test_unknown_cost_aggregates_to_null_not_zero():
    report = EvaluationRunner(UnknownCostStrategy()).run(_dataset(), _corpus())
    assert all(case.cost_usd is None for case in report.cases)
    assert report.aggregate.cost_total_usd is None


def test_mixed_known_and_unknown_cost_aggregates_null_not_zero(tmp_path: Path):
    """Any unknown cost makes the aggregate total unknown, never a fake 0.0.

    One row reporting the known offline cost 0.0 does not make the
    overall total a measured zero while another row is unknown.
    """

    class MixedCostStrategy(RecordingStrategy):
        def run(self, case, corpus):
            output = super().run(case, corpus)
            cost = None if case.case_id != "seed-001" else 0.0
            return StrategyOutput(
                case_id=output.case_id,
                status=output.status,
                answer=output.answer,
                cost_usd=cost,
                tool_calls=output.tool_calls,
                topic_recall=output.topic_recall,
                source_coverage=output.source_coverage,
                limitations=output.limitations,
            )

    report = EvaluationRunner(MixedCostStrategy()).run(
        _dataset(), _corpus(), output_dir=tmp_path
    )
    assert report.cases[0].cost_usd == 0.0
    assert all(case.cost_usd is None for case in report.cases[1:])
    # Fail-closed: one unknown row makes the aggregate total unknown (None),
    # even though the other rows report the known offline cost 0.0.
    assert report.aggregate.cost_total_usd is None

    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "| cost_total_usd | n/a |" in summary
    assert "| cost_total_usd | 0.0 |" not in summary


def test_aggregate_cost_total_is_null_when_any_case_cost_is_unknown():
    """Focused reproduction: mixed known/unknown costs must not total 0.0."""
    mixed = _aggregate(
        (
            CaseResult(case_id="seed-001", status="success", answer="a", cost_usd=0.0),
            CaseResult(case_id="seed-002", status="success", answer="b", cost_usd=None),
        )
    )
    assert mixed.cost_total_usd is None

    all_known = _aggregate(
        (
            CaseResult(case_id="seed-001", status="success", answer="a", cost_usd=0.0),
            CaseResult(case_id="seed-002", status="success", answer="b", cost_usd=0.0),
        )
    )
    assert all_known.cost_total_usd == 0.0


# ---------------------------------------------------------------------------
# Redaction covers the new fingerprint/report fields
# ---------------------------------------------------------------------------


def test_new_fingerprint_fields_never_leak_secrets_or_absolute_paths(
    tmp_path: Path,
):
    class EvilStrategy(RecordingStrategy):
        strategy_id = "/Users/evil/strategy"
        model_id = "mock:deterministic"
        prompt_id = "sk-1234567890abcdef"
        prompt_sha256 = "/etc/passwd"
        config_sha256 = "Bearer abcdef123456"

        def run(self, case, corpus):
            output = super().run(case, corpus)
            return StrategyOutput(
                case_id=output.case_id,
                status=output.status,
                answer="answer with sk-0987654321secret",
                limitations=("uses /Users/evil/limitation",),
            )

    EvaluationRunner(EvilStrategy()).run(_dataset(), _corpus(), output_dir=tmp_path)
    manifest = _manifest_dict(tmp_path / "manifest.json")

    # Fingerprints are canonical hashes over the *redacted* manifest
    # values, so they are 64-hex and can never smuggle secrets.
    assert _SHA256_HEX_RE.fullmatch(manifest["run_fingerprint"])
    assert _SHA256_HEX_RE.fullmatch(manifest["input_fingerprint"])
    assert isinstance(manifest["git_dirty"], bool)

    for name in ("manifest.json", "cases.jsonl", "summary.md"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert "/Users/" not in text
        assert "sk-" not in text
        assert "Bearer" not in text
        assert "/etc/" not in text
