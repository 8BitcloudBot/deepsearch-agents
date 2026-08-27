"""Integration: S0 vs S1 comparison on seed-10 (P3-4).

Proves the comparison contract: S0 and S1 each yield exactly ten
ordered terminal results over the same immutable dataset/corpus, the
comparison is keyed by identical fingerprint fields except
strategy/prompt/config, a mismatched fingerprint is rejected, the
comparison report never claims S1 wins (offline proxies only), the
comparison writer obeys the versioned-data guard, and the CLI
``--compare`` mode runs both strategies under one output root and
writes ``comparison.md``.
"""

import json
import re
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from app.evaluation.datasets import load_dataset
from app.evaluation.reporting import (
    render_strategy_comparison_markdown,
    write_strategy_comparison,
)
from app.evaluation.runner import EvaluationRunner
from app.evaluation.source_corpus import load_corpus
from app.evaluation.strategies.s0_single_agent import S0SingleAgentStrategy
from app.evaluation.strategies.s1_orchestrator_workers import (
    S1OrchestratorWorkersStrategy,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SEED_IDS = [f"seed-{i:03d}" for i in range(1, 11)]
_DATA_PHASE3 = REPO_ROOT / "data" / "phase3"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture(scope="module")
def s0_report():
    dataset = load_dataset()
    return EvaluationRunner(S0SingleAgentStrategy()).run(dataset, load_corpus())


@pytest.fixture(scope="module")
def s1_report():
    dataset = load_dataset()
    return EvaluationRunner(S1OrchestratorWorkersStrategy()).run(dataset, load_corpus())


def test_s0_and_s1_each_yield_ten_terminal_results(s0_report, s1_report):
    for report in (s0_report, s1_report):
        assert [case.case_id for case in report.cases] == SEED_IDS
        assert report.aggregate.total == 10
        assert report.aggregate.success == 10
        assert all(case.status == "success" for case in report.cases)
    assert s0_report.manifest.dataset_id == s1_report.manifest.dataset_id
    assert s0_report.manifest.corpus_sha256 == s1_report.manifest.corpus_sha256
    assert s0_report.manifest.dataset_sha256 == s1_report.manifest.dataset_sha256


def test_comparison_requires_identical_fingerprints_except_strategy_prompt_config(
    s0_report, s1_report
):
    # Real runs over the same dataset/corpus compare cleanly.
    markdown = render_strategy_comparison_markdown(s0_report, s1_report)
    assert "s0-single-agent" in markdown
    assert "s1-orchestrator-workers" in markdown

    # Tampering with a comparable fingerprint field must be rejected.
    tampered = replace(
        s1_report,
        manifest=replace(s1_report.manifest, dataset_sha256="ab" * 32),
    )
    with pytest.raises(ValueError, match="dataset_sha256"):
        render_strategy_comparison_markdown(s0_report, tampered)


def test_comparison_is_keyed_by_identical_fingerprint_fields(s0_report, s1_report):
    markdown = render_strategy_comparison_markdown(s0_report, s1_report)
    for field in (
        "dataset_id",
        "dataset_sha256",
        "corpus_id",
        "corpus_sha256",
        "model_id",
        "execution_mode",
        "runner_version",
        "git_commit",
    ):
        assert f"- **{field}:" in markdown
        assert getattr(s0_report.manifest, field) in markdown
        assert getattr(s1_report.manifest, field) in markdown
    # Strategy/prompt/config differ by design and are both listed.
    for field in ("strategy_id", "prompt_id", "prompt_sha256", "config_sha256"):
        assert getattr(s0_report.manifest, field) in markdown
        assert getattr(s1_report.manifest, field) in markdown
    # Every case has a terminal row in both strategies.
    for case_id in SEED_IDS:
        assert case_id in markdown
    assert "| s0-single-agent |" in markdown
    assert "| s1-orchestrator-workers |" in markdown


def test_comparison_never_claims_a_winner(s0_report, s1_report):
    markdown = render_strategy_comparison_markdown(s0_report, s1_report).lower()
    # No subjective superiority language; only measured numbers.
    assert "wins" not in markdown
    assert "is better" not in markdown
    assert "outperforms" not in markdown
    # Offline-proxy framing is present.
    assert "offline" in markdown
    assert "proxy" in markdown
    # Both aggregate columns carry the same ten-case totals.
    assert "| 10 | 10 |" in markdown


def test_write_strategy_comparison_writes_one_file(
    tmp_path: Path, s0_report, s1_report
):
    paths = write_strategy_comparison(tmp_path, s0_report, s1_report)
    assert paths["comparison"].name == "comparison.md"
    assert (tmp_path / "comparison.md").is_file()
    text = (tmp_path / "comparison.md").read_text(encoding="utf-8")
    assert text.startswith("#")
    assert "s0-single-agent" in text
    assert "s1-orchestrator-workers" in text


def test_write_strategy_comparison_refuses_versioned_data_dir(
    s0_report, s1_report, tmp_path: Path
):
    alias = tmp_path / "alias-to-data-phase3"
    alias.symlink_to(_DATA_PHASE3, target_is_directory=True)
    with pytest.raises(ValueError, match="refusing"):
        write_strategy_comparison(alias, s0_report, s1_report)
    assert not (alias / "comparison.md").exists()


def test_cli_compare_runs_both_strategies_and_writes_comparison(tmp_path: Path):
    out = tmp_path / "compare-out"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate.py",
            "--dataset",
            "seed-10",
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
    assert s0_manifest["dataset_sha256"] == s1_manifest["dataset_sha256"]
    assert s0_manifest["corpus_sha256"] == s1_manifest["corpus_sha256"]
    assert s0_manifest["model_id"] == s1_manifest["model_id"] == "mock:deterministic"
    assert len(_read_jsonl(out / "s0" / "cases.jsonl")) == 10
    assert len(_read_jsonl(out / "s1" / "cases.jsonl")) == 10

    comparison = (out / "comparison.md").read_text(encoding="utf-8")
    assert "s0-single-agent" in comparison
    assert "s1-orchestrator-workers" in comparison
    assert re.fullmatch(r"[0-9a-f]{40}", s0_manifest["git_commit"])
