"""Integration: dev-40 executed end-to-end with S1 Orchestrator-Workers (P3-5).

Runs the real runner and CLI over the frozen dev-40 dataset (selected
by name through the multi-dataset registry) and proves: forty terminal
case rows in stable order dev-001..dev-040, aggregate counts, worker
boundaries preserved in every answer, fingerprint fields, truthful
unmeasured latency, and the CLI entry point ``--dataset dev-40
--strategy s1 --offline`` (forty rows, no silent omissions).
"""

import json
import re
import subprocess
import sys
from pathlib import Path

from app.evaluation.datasets import load_dataset_by_name
from app.evaluation.runner import EvaluationRunner
from app.evaluation.source_contracts import corpus_sha256
from app.evaluation.source_corpus import load_corpus
from app.evaluation.strategies.s1_orchestrator_workers import (
    S1OrchestratorWorkersStrategy,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEV_IDS = [f"dev-{i:03d}" for i in range(1, 41)]
_ABS_PATH_RE = re.compile(r"(?:/Users/|/tmp/|/private/)")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_runner_executes_all_dev_cases_with_s1():
    dataset = load_dataset_by_name("dev-40")
    corpus = load_corpus()
    report = EvaluationRunner(S1OrchestratorWorkersStrategy()).run(dataset, corpus)

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
    assert report.manifest.strategy_id == "s1-orchestrator-workers"
    assert report.manifest.model_id == "mock:deterministic"
    assert report.manifest.execution_mode == "offline"
    assert report.manifest.dataset_id == "dev-40-v1"
    # Worker boundaries survive into the report answers for every case.
    assert all("## Worker boundaries" in case.answer for case in report.cases)


def test_reports_are_machine_readable_with_fingerprints(tmp_path: Path):
    dataset = load_dataset_by_name("dev-40")
    corpus = load_corpus()
    EvaluationRunner(S1OrchestratorWorkersStrategy()).run(
        dataset, corpus, output_dir=tmp_path
    )

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["dataset_id"] == "dev-40-v1"
    assert manifest["dataset_sha256"] == dataset.file_sha256
    assert manifest["corpus_id"] == corpus.corpus_id
    assert manifest["corpus_sha256"] == corpus_sha256(corpus)
    assert manifest["strategy_id"] == "s1-orchestrator-workers"
    assert manifest["model_id"] == "mock:deterministic"
    assert manifest["prompt_id"] == "s1-orchestrator-workers-v1"
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
    EvaluationRunner(S1OrchestratorWorkersStrategy()).run(
        dataset, corpus, output_dir=tmp_path
    )

    for name in ("manifest.json", "cases.jsonl", "summary.md"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert str(tmp_path) not in text
        assert not _ABS_PATH_RE.search(text)


def test_cli_runs_dev40_s1_offline_and_writes_reports(tmp_path: Path):
    out = tmp_path / "cli-out"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate.py",
            "--dataset",
            "dev-40",
            "--strategy",
            "s1",
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
