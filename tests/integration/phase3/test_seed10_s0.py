"""Integration: seed-10 executed end-to-end with S0 Single Agent (P3-3).

Runs the real runner over the frozen seed-10 dataset and versioned
corpus twice into separate output directories and proves: ten terminal
case rows in stable order, aggregate counts, the three report files
(manifest.json / cases.jsonl / summary.md), fingerprint fields
(dataset/corpus hashes, strategy, mock model, prompt/config, git
commit, offline mode), no absolute paths, deterministic reruns, truthful
unmeasured latency (``null``/``n/a``), git provenance even when the CLI
is launched from outside the repo, and the CLI entry point.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

from app.evaluation.datasets import load_dataset
from app.evaluation.runner import EvaluationRunner
from app.evaluation.strategies.s0_single_agent import S0SingleAgentStrategy
from app.research.contracts import corpus_sha256
from app.research.corpus import load_corpus

REPO_ROOT = Path(__file__).resolve().parents[3]
SEED_IDS = [f"seed-{i:03d}" for i in range(1, 11)]
_ABS_PATH_RE = re.compile(r"(?:/Users/|/tmp/|/private/)")
_DATA_PHASE3 = REPO_ROOT / "data" / "phase3"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_seed10_loads_ten_cases_in_order():
    dataset = load_dataset()
    assert dataset.dataset_id == "seed-10-v1"
    assert dataset.case_count == 10
    assert [case.case_id for case in dataset.cases] == SEED_IDS


def test_runner_executes_all_seed_cases_with_s0():
    dataset = load_dataset()
    corpus = load_corpus()
    report = EvaluationRunner(S0SingleAgentStrategy()).run(dataset, corpus)

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
    assert report.manifest.strategy_id == "s0-single-agent"
    assert report.manifest.model_id == "mock:deterministic"
    assert report.manifest.execution_mode == "offline"


def test_reports_are_machine_readable_with_fingerprints(tmp_path: Path):
    dataset = load_dataset()
    corpus = load_corpus()
    EvaluationRunner(S0SingleAgentStrategy()).run(dataset, corpus, output_dir=tmp_path)

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["dataset_id"] == "seed-10-v1"
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
    assert len(rows) == 10
    assert [row["case_id"] for row in rows] == SEED_IDS
    assert all(row["status"] == "success" for row in rows)
    assert all(row["cost_usd"] == 0.0 for row in rows)
    assert all(row["latency_ms"] is None for row in rows)

    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "| latency_mean_ms | n/a |" in summary


def test_no_absolute_paths_in_any_report_file(tmp_path: Path):
    dataset = load_dataset()
    corpus = load_corpus()
    EvaluationRunner(S0SingleAgentStrategy()).run(dataset, corpus, output_dir=tmp_path)

    for name in ("manifest.json", "cases.jsonl", "summary.md"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert str(tmp_path) not in text
        assert not _ABS_PATH_RE.search(text)


def test_two_runs_are_deterministic_except_run_id_and_started_at(tmp_path: Path):
    dataset = load_dataset()
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


def test_summary_markdown_contains_aggregates_and_case_rows(tmp_path: Path):
    dataset = load_dataset()
    corpus = load_corpus()
    EvaluationRunner(S0SingleAgentStrategy()).run(dataset, corpus, output_dir=tmp_path)

    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert summary.startswith("#")
    assert "seed-10-v1" in summary
    assert "s0-single-agent" in summary
    assert "mock:deterministic" in summary
    assert "offline" in summary
    for case_id in SEED_IDS:
        assert case_id in summary
    assert "Limitations" in summary


def test_cli_runs_seed10_s0_offline_and_writes_reports(tmp_path: Path):
    out = tmp_path / "cli-out"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate.py",
            "--dataset",
            "seed-10",
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
    assert len(_read_jsonl(out / "cases.jsonl")) == 10


def test_cli_rejects_unknown_strategy_and_missing_offline(tmp_path: Path):
    result = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate.py",
            "--dataset",
            "seed-10",
            "--strategy",
            "s1-orchestrator-workers",
            "--offline",
            "--output",
            str(tmp_path / "x"),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0

    result = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate.py",
            "--dataset",
            "seed-10",
            "--strategy",
            "s0",
            "--output",
            str(tmp_path / "y"),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "offline" in result.stderr.lower()


def _run_cli(out_dir: Path, cwd=REPO_ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            "scripts/evaluate.py",
            "--dataset",
            "seed-10",
            "--strategy",
            "s0",
            "--offline",
            "--output",
            str(out_dir),
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_two_cli_runs_compare_stable_fields(tmp_path: Path):
    """True two-CLI-run comparison: stable fields equal, run-specific
    fields excluded, latency null in both."""
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()

    first_dir, second_dir = tmp_path / "cli-a", tmp_path / "cli-b"
    first = _run_cli(first_dir)
    second = _run_cli(second_dir)
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr

    first_manifest = json.loads(
        (first_dir / "manifest.json").read_text(encoding="utf-8")
    )
    second_manifest = json.loads(
        (second_dir / "manifest.json").read_text(encoding="utf-8")
    )
    assert first_manifest["git_commit"] == head
    assert second_manifest["git_commit"] == head
    first_run_id = first_manifest.pop("run_id")
    second_run_id = second_manifest.pop("run_id")
    first_started = first_manifest.pop("started_at")
    second_started = second_manifest.pop("started_at")
    assert first_run_id != second_run_id
    assert first_manifest == second_manifest

    first_rows = _read_jsonl(first_dir / "cases.jsonl")
    second_rows = _read_jsonl(second_dir / "cases.jsonl")
    assert first_rows == second_rows
    assert all(row["latency_ms"] is None for row in first_rows)

    first_summary = (first_dir / "summary.md").read_text(encoding="utf-8")
    second_summary = (second_dir / "summary.md").read_text(encoding="utf-8")
    # Each summary is normalized independently against its own volatile
    # fields; timestamps may legitimately differ between the two runs.
    first_summary = first_summary.replace(first_run_id, "X").replace(first_started, "X")
    second_summary = second_summary.replace(second_run_id, "X").replace(
        second_started, "X"
    )
    assert first_summary == second_summary


def test_cli_launched_from_outside_repo_records_git_head(tmp_path: Path):
    """Git provenance must come from this checkout, not the cwd: launch
    the CLI by absolute script path from a directory outside the repo."""
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
            "s0",
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
    """CLI must refuse an output dir that aliases data/phase3 and leave
    the versioned dataset manifest untouched."""
    manifest_path = _DATA_PHASE3 / "datasets" / "manifest.json"
    before = manifest_path.read_bytes()
    alias = tmp_path / "alias-to-data-phase3"
    alias.symlink_to(_DATA_PHASE3, target_is_directory=True)

    result = _run_cli(alias)
    assert result.returncode != 0
    assert "error" in result.stderr.lower()
    assert manifest_path.read_bytes() == before
    assert not (alias / "manifest.json").exists()
