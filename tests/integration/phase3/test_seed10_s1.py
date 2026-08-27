"""Integration: seed-10 executed end-to-end with S1 Orchestrator-Workers (P3-4).

Runs the real runner over the frozen seed-10 dataset and versioned
corpus twice into separate output directories and proves: ten terminal
case rows in stable order, aggregate counts, the three report files
(manifest.json / cases.jsonl / summary.md), fingerprint fields
(dataset/corpus hashes, ``s1-orchestrator-workers`` strategy, mock
model, prompt/config, git commit, offline mode), no absolute paths,
deterministic reruns, truthful unmeasured latency (``null``/``n/a``),
git provenance from outside the repo, CLI selection via ``--strategy
s1``, and versioned-data write protection.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

from app.evaluation.datasets import load_dataset
from app.evaluation.runner import EvaluationRunner
from app.evaluation.source_contracts import corpus_sha256
from app.evaluation.source_corpus import load_corpus
from app.evaluation.strategies.s1_orchestrator_workers import (
    S1OrchestratorWorkersStrategy,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SEED_IDS = [f"seed-{i:03d}" for i in range(1, 11)]
_ABS_PATH_RE = re.compile(r"(?:/Users/|/tmp/|/private/)")
_DATA_PHASE3 = REPO_ROOT / "data" / "phase3"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_runner_executes_all_seed_cases_with_s1():
    dataset = load_dataset()
    corpus = load_corpus()
    report = EvaluationRunner(S1OrchestratorWorkersStrategy()).run(dataset, corpus)

    assert [case.case_id for case in report.cases] == SEED_IDS
    assert all(case.status == "success" for case in report.cases)
    assert all(case.latency_ms is None for case in report.cases)
    assert report.aggregate.total == 10
    assert report.aggregate.success == 10
    assert report.aggregate.failed == 0
    assert report.aggregate.skipped == 0
    assert report.aggregate.cost_total_usd == 0.0
    assert report.aggregate.latency_mean_ms is None
    assert report.aggregate.latency_median_ms is None
    assert report.aggregate.latency_max_ms is None
    assert report.manifest.strategy_id == "s1-orchestrator-workers"
    assert report.manifest.model_id == "mock:deterministic"
    assert report.manifest.execution_mode == "offline"
    # Worker boundaries survive into the report answers.
    assert all("## Worker boundaries" in case.answer for case in report.cases)


def test_reports_are_machine_readable_with_fingerprints(tmp_path: Path):
    dataset = load_dataset()
    corpus = load_corpus()
    EvaluationRunner(S1OrchestratorWorkersStrategy()).run(
        dataset, corpus, output_dir=tmp_path
    )

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["dataset_id"] == "seed-10-v1"
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
    assert len(rows) == 10
    assert [row["case_id"] for row in rows] == SEED_IDS
    assert all(row["status"] == "success" for row in rows)
    assert all(row["cost_usd"] == 0.0 for row in rows)
    assert all(row["latency_ms"] is None for row in rows)
    assert all("Worker boundaries" in row["answer"] for row in rows)

    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "| latency_mean_ms | n/a |" in summary


def test_no_absolute_paths_in_any_report_file(tmp_path: Path):
    dataset = load_dataset()
    corpus = load_corpus()
    EvaluationRunner(S1OrchestratorWorkersStrategy()).run(
        dataset, corpus, output_dir=tmp_path
    )

    for name in ("manifest.json", "cases.jsonl", "summary.md"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert str(tmp_path) not in text
        assert not _ABS_PATH_RE.search(text)


def test_two_runs_are_deterministic_except_run_id_and_started_at(tmp_path: Path):
    dataset = load_dataset()
    corpus = load_corpus()
    first_dir, second_dir = tmp_path / "a", tmp_path / "b"

    EvaluationRunner(S1OrchestratorWorkersStrategy()).run(
        dataset, corpus, output_dir=first_dir
    )
    EvaluationRunner(S1OrchestratorWorkersStrategy()).run(
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
    first_manifest.pop("run_id")
    second_manifest.pop("run_id")
    first_manifest.pop("started_at")
    second_manifest.pop("started_at")
    assert first_manifest == second_manifest


def test_cli_runs_seed10_s1_offline_and_writes_reports(tmp_path: Path):
    out = tmp_path / "cli-out"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate.py",
            "--dataset",
            "seed-10",
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
    assert "s1-orchestrator-workers" in result.stdout
    assert out.is_dir()
    assert sorted(p.name for p in out.iterdir()) == [
        "cases.jsonl",
        "manifest.json",
        "summary.md",
    ]
    assert len(_read_jsonl(out / "cases.jsonl")) == 10


def test_cli_launched_from_outside_repo_records_git_head(tmp_path: Path):
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()

    out = tmp_path / "cli-from-tmp"
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "evaluate.py"),
            "--dataset",
            "seed-10",
            "--strategy",
            "s1",
            "--offline",
            "--output",
            str(out),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["git_commit"] == head
    assert re.fullmatch(r"[0-9a-f]{40}", manifest["git_commit"])


def test_cli_rejects_output_into_data_phase3_via_symlink(tmp_path: Path):
    manifest_path = _DATA_PHASE3 / "datasets" / "manifest.json"
    before = manifest_path.read_bytes()
    alias = tmp_path / "alias-to-data-phase3"
    alias.symlink_to(_DATA_PHASE3, target_is_directory=True)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate.py",
            "--dataset",
            "seed-10",
            "--strategy",
            "s1",
            "--offline",
            "--output",
            str(alias),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "error" in result.stderr.lower()
    assert manifest_path.read_bytes() == before
    assert not (alias / "manifest.json").exists()
