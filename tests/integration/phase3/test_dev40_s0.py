"""Integration: dev-40 executed end-to-end with S0 Single Agent (P3-5).

Runs the real runner and CLI over the frozen dev-40 dataset (selected
by name through the multi-dataset registry) and proves: forty terminal
case rows in stable order dev-001..dev-040, aggregate counts, the three
report files, fingerprint fields, no absolute paths, deterministic
reruns, truthful unmeasured latency, and the CLI entry points
``--dataset dev-40 --strategy s0 --offline`` and ``--dataset dev-40
--compare --offline`` (both strategies, forty rows each).
"""

import json
import re
import subprocess
import sys
from pathlib import Path

from benchmarks.evaluation.datasets import load_dataset_by_name
from benchmarks.evaluation.runner import EvaluationRunner
from benchmarks.evaluation.source_contracts import corpus_sha256
from benchmarks.evaluation.source_corpus import load_corpus
from benchmarks.evaluation.strategies.s0_single_agent import S0SingleAgentStrategy

REPO_ROOT = Path(__file__).resolve().parents[3]
DEV_IDS = [f"dev-{i:03d}" for i in range(1, 41)]
_ABS_PATH_RE = re.compile(r"(?:/Users/|/tmp/|/private/)")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_dev40_loads_forty_cases_in_order():
    dataset = load_dataset_by_name("dev-40")
    assert dataset.dataset_id == "dev-40-v1"
    assert dataset.case_count == 40
    assert [case.case_id for case in dataset.cases] == DEV_IDS


def test_runner_executes_all_dev_cases_with_s0():
    dataset = load_dataset_by_name("dev-40")
    corpus = load_corpus()
    report = EvaluationRunner(S0SingleAgentStrategy()).run(dataset, corpus)

    assert [case.case_id for case in report.cases] == DEV_IDS
    assert all(case.status == "success" for case in report.cases)
    assert all(case.latency_ms is None for case in report.cases)
    assert report.aggregate.total == 40
    assert report.aggregate.success == 40
    assert report.aggregate.failed == 0
    assert report.aggregate.skipped == 0
    assert report.aggregate.cost_total_usd == 0.0
    assert report.aggregate.latency_mean_ms is None
    assert report.aggregate.latency_median_ms is None
    assert report.aggregate.latency_max_ms is None
    assert report.manifest.strategy_id == "s0-single-agent"
    assert report.manifest.model_id == "mock:deterministic"
    assert report.manifest.execution_mode == "offline"
    assert report.manifest.dataset_id == "dev-40-v1"


def test_reports_are_machine_readable_with_fingerprints(tmp_path: Path):
    dataset = load_dataset_by_name("dev-40")
    corpus = load_corpus()
    EvaluationRunner(S0SingleAgentStrategy()).run(dataset, corpus, output_dir=tmp_path)

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["dataset_id"] == "dev-40-v1"
    assert manifest["dataset_sha256"] == dataset.file_sha256
    assert manifest["corpus_id"] == corpus.corpus_id
    assert manifest["corpus_sha256"] == corpus_sha256(corpus)
    assert manifest["strategy_id"] == "s0-single-agent"
    assert manifest["model_id"] == "mock:deterministic"
    assert manifest["prompt_id"] == "s0-single-agent-v1"
    assert manifest["execution_mode"] == "offline"
    assert re.fullmatch(r"[0-9a-f]{40}", manifest["git_commit"])
    assert re.fullmatch(r"[0-9a-f]{64}", manifest["prompt_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", manifest["config_sha256"])

    rows = _read_jsonl(tmp_path / "cases.jsonl")
    assert len(rows) == 40
    assert [row["case_id"] for row in rows] == DEV_IDS
    assert all(row["status"] == "success" for row in rows)
    assert all(row["cost_usd"] == 0.0 for row in rows)
    assert all(row["latency_ms"] is None for row in rows)


def test_no_absolute_paths_in_any_report_file(tmp_path: Path):
    dataset = load_dataset_by_name("dev-40")
    corpus = load_corpus()
    EvaluationRunner(S0SingleAgentStrategy()).run(dataset, corpus, output_dir=tmp_path)

    for name in ("manifest.json", "cases.jsonl", "summary.md"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert str(tmp_path) not in text
        assert not _ABS_PATH_RE.search(text)


def test_two_runs_are_deterministic_except_run_id_and_started_at(tmp_path: Path):
    dataset = load_dataset_by_name("dev-40")
    corpus = load_corpus()
    first_dir, second_dir = tmp_path / "a", tmp_path / "b"

    EvaluationRunner(S0SingleAgentStrategy()).run(dataset, corpus, output_dir=first_dir)
    EvaluationRunner(S0SingleAgentStrategy()).run(
        dataset, corpus, output_dir=second_dir
    )

    assert (first_dir / "cases.jsonl").read_bytes() == (
        second_dir / "cases.jsonl"
    ).read_bytes()

    first_manifest = json.loads(
        (first_dir / "manifest.json").read_text(encoding="utf-8")
    )
    second_manifest = json.loads(
        (second_dir / "manifest.json").read_text(encoding="utf-8")
    )
    first_run_id = first_manifest.pop("run_id")
    second_run_id = second_manifest.pop("run_id")
    first_manifest.pop("started_at")
    second_manifest.pop("started_at")
    assert first_run_id != second_run_id
    assert first_manifest == second_manifest


def test_summary_markdown_contains_aggregates_and_case_rows(tmp_path: Path):
    dataset = load_dataset_by_name("dev-40")
    corpus = load_corpus()
    EvaluationRunner(S0SingleAgentStrategy()).run(dataset, corpus, output_dir=tmp_path)

    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert summary.startswith("#")
    assert "dev-40-v1" in summary
    assert "s0-single-agent" in summary
    assert "mock:deterministic" in summary
    assert "offline" in summary
    for case_id in DEV_IDS:
        assert case_id in summary
    assert "Limitations" in summary


def test_cli_runs_dev40_s0_offline_and_writes_reports(tmp_path: Path):
    out = tmp_path / "cli-out"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate.py",
            "--dataset",
            "dev-40",
            "--strategy",
            "s0",
            "--offline",
            "--output",
            str(out),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert out.is_dir()
    assert sorted(p.name for p in out.iterdir()) == [
        "cases.jsonl",
        "manifest.json",
        "summary.md",
    ]
    assert len(_read_jsonl(out / "cases.jsonl")) == 40


def test_cli_compare_runs_both_strategies_on_dev40(tmp_path: Path):
    out = tmp_path / "compare-out"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate.py",
            "--dataset",
            "dev-40",
            "--compare",
            "--offline",
            "--output",
            str(out),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    s0_manifest = json.loads((out / "s0" / "manifest.json").read_text(encoding="utf-8"))
    s1_manifest = json.loads((out / "s1" / "manifest.json").read_text(encoding="utf-8"))
    assert s0_manifest["strategy_id"] == "s0-single-agent"
    assert s1_manifest["strategy_id"] == "s1-orchestrator-workers"
    assert s0_manifest["dataset_id"] == s1_manifest["dataset_id"] == "dev-40-v1"
    assert s0_manifest["dataset_sha256"] == s1_manifest["dataset_sha256"]
    assert s0_manifest["corpus_sha256"] == s1_manifest["corpus_sha256"]
    assert s0_manifest["model_id"] == s1_manifest["model_id"] == "mock:deterministic"
    assert len(_read_jsonl(out / "s0" / "cases.jsonl")) == 40
    assert len(_read_jsonl(out / "s1" / "cases.jsonl")) == 40

    comparison = (out / "comparison.md").read_text(encoding="utf-8")
    assert "s0-single-agent" in comparison
    assert "s1-orchestrator-workers" in comparison
    assert "| 40 | 40 |" in comparison
