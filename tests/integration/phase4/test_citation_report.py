"""Integration tests for the offline citation evaluation report (P4-4).

Runs ``scripts/evaluate_citations.py`` twice and proves the report is
deterministic: stable partition rows and fingerprints across runs, volatile
``report_id``/``generated_at`` excluded from the report fingerprint, the three
required partitions present and never mixed, and provenance bound to the
frozen dataset/corpus manifests and the Git commit.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.citations.metrics import PartitionMetrics, Pipeline, compute_partition_metrics
from app.citations.reporting import REPORT_SCHEMA_VERSION, build_report

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]
CLI = REPO_ROOT / "scripts" / "evaluate_citations.py"
FIXTURE_FINGERPRINT = (
    "3e222d1aed75512236eff80a5a4528aa"  # pragma: allowlist secret
    "93e047224f3d0033ab389976dc83a090"  # pragma: allowlist secret
)
DATASET_FILE_SHA256 = (
    "a902aba483f89285b02792369963ce5e"  # pragma: allowlist secret
    "db35f3460abfdcc1b7f712b0e8cf1055"  # pragma: allowlist secret
)


def run_cli(tmp_path: Path, tag: str) -> Path:
    out_dir = tmp_path / tag
    result = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--dataset",
            "seed-10",
            "--offline",
            "--output",
            str(out_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert (out_dir / "report.json").is_file()
    assert (out_dir / "partitions.jsonl").is_file()
    return out_dir


def load_report(out_dir: Path) -> dict:
    return json.loads((out_dir / "report.json").read_text(encoding="utf-8"))


def load_rows(out_dir: Path) -> list[dict]:
    text = (out_dir / "partitions.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line]


def test_cli_runs_twice_with_stable_rows_and_fingerprints(tmp_path: Path) -> None:
    out_a = run_cli(tmp_path, "a")
    out_b = run_cli(tmp_path, "b")
    report_a = load_report(out_a)
    report_b = load_report(out_b)

    # volatile fields are present and differ between runs; everything else is
    # byte-identical, including the report fingerprint.
    assert report_a["report_id"] and report_b["report_id"]
    assert report_a["report_id"] != report_b["report_id"]
    assert report_a["generated_at"] and report_b["generated_at"]
    assert report_a["report_fingerprint"] == report_b["report_fingerprint"]
    stripped = {
        k: v for k, v in report_a.items() if k not in ("report_id", "generated_at")
    }
    assert stripped == {
        k: v for k, v in report_b.items() if k not in ("report_id", "generated_at")
    }

    rows_a = load_rows(out_a)
    rows_b = load_rows(out_b)
    assert rows_a == rows_b
    assert [row["partition_id"] for row in rows_a] == [
        "rule/offline",
        "semantic/mock",
        "semantic/real",
    ]
    assert all(row["fingerprint"] for row in rows_a)


def test_report_contains_required_partitions_and_metric_values(tmp_path: Path) -> None:
    report = load_report(run_cli(tmp_path, "a"))
    assert report["schema_version"] == REPORT_SCHEMA_VERSION
    assert set(report["partitions"]) == {
        "rule/offline",
        "semantic/mock",
        "semantic/real",
    }

    rule = report["partitions"]["rule/offline"]["metrics"]
    assert rule["citation_precision"] == {
        "value": 1.0,
        "numerator": 6,
        "denominator": 6,
        "limitation": None,
    }
    assert rule["citation_recall"] == {
        "value": 0.75,
        "numerator": 6,
        "denominator": 8,
        "limitation": None,
    }
    assert rule["entailment"] == {
        "value": 0.6,
        "numerator": 6,
        "denominator": 10,
        "limitation": None,
    }
    assert rule["unsupported_claim_rate"] == {
        "value": 0.4,
        "numerator": 4,
        "denominator": 10,
        "limitation": None,
    }

    mock = report["partitions"]["semantic/mock"]["metrics"]
    assert mock["citation_precision"] == {
        "value": 0.857143,
        "numerator": 6,
        "denominator": 7,
        "limitation": None,
    }
    assert mock["citation_recall"] == {
        "value": 0.75,
        "numerator": 6,
        "denominator": 8,
        "limitation": None,
    }
    assert mock["entailment"] == {
        "value": 0.7,
        "numerator": 7,
        "denominator": 10,
        "limitation": None,
    }
    assert mock["unsupported_claim_rate"] == {
        "value": 0.3,
        "numerator": 3,
        "denominator": 10,
        "limitation": None,
    }

    real = report["partitions"]["semantic/real"]["metrics"]
    for name in (
        "citation_precision",
        "citation_recall",
        "entailment",
        "unsupported_claim_rate",
    ):
        mv = real[name]
        assert mv["value"] is None
        assert mv["numerator"] == 0
        assert mv["denominator"] == 0
        assert mv["limitation"]


def test_report_provenance_binds_dataset_corpus_and_git(tmp_path: Path) -> None:
    report = load_report(run_cli(tmp_path, "a"))
    prov = report["provenance"]
    assert prov["dataset_id"] == "seed-10-v1"
    assert prov["dataset_file_sha256"] == DATASET_FILE_SHA256
    assert prov["case_count"] == 10
    assert prov["corpus_id"] == "agent-research-corpus-v1"
    assert prov["fixture_fingerprint"] == FIXTURE_FINGERPRINT
    assert prov["git_commit"]
    assert prov["runner"]["name"] == "evaluate_citations"


def test_semantic_mock_provenance_carries_fingerprints(tmp_path: Path) -> None:
    report = load_report(run_cli(tmp_path, "a"))
    mock_prov = report["partitions"]["semantic/mock"]["provenance"]
    assert mock_prov["model_id"] == "mock:deterministic"
    assert mock_prov["prompt_id"] == "p4-semantic-support-v1"
    assert len(mock_prov["prompt_sha256"]) == 64
    assert len(mock_prov["config_sha256"]) == 64
    assert mock_prov["prompt_sha256"] == mock_prov["prompt_sha256"]

    rule_prov = report["partitions"]["rule/offline"]["provenance"]
    assert rule_prov["adapter"] == "rule:offline"
    assert rule_prov["model_id"] is None


def _empty_partitions() -> list[PartitionMetrics]:
    return [
        compute_partition_metrics(
            pipeline=Pipeline.RULE,
            mode="offline",
            claims=(),
            citations=(),
            judgments=(),
        ),
        compute_partition_metrics(
            pipeline=Pipeline.SEMANTIC,
            mode="mock",
            claims=(),
            citations=(),
            judgments=(),
        ),
        compute_partition_metrics(
            pipeline=Pipeline.SEMANTIC,
            mode="real",
            claims=(),
            citations=(),
            judgments=(),
        ),
    ]


def test_build_report_fingerprint_excludes_volatile_fields() -> None:
    fixture_manifest = json.loads(
        (REPO_ROOT / "data/phase4/citations/manifest.json").read_text(encoding="utf-8")
    )
    dataset_manifest = json.loads(
        (REPO_ROOT / "data/phase3/datasets/manifest.json").read_text(encoding="utf-8")
    )
    sources_manifest = json.loads(
        (REPO_ROOT / "data/phase3/sources/manifest.json").read_text(encoding="utf-8")
    )
    partitions = _empty_partitions()
    first = build_report(
        partitions=partitions,
        fixture_manifest=fixture_manifest,
        dataset_manifest=dataset_manifest,
        sources_manifest=sources_manifest,
        git_commit="0123456789abcdef",  # pragma: allowlist secret
        report_id="id-1",
        generated_at="2026-01-01T00:00:00+00:00",
    )
    second = build_report(
        partitions=partitions,
        fixture_manifest=fixture_manifest,
        dataset_manifest=dataset_manifest,
        sources_manifest=sources_manifest,
        git_commit="0123456789abcdef",  # pragma: allowlist secret
        report_id="id-2",
        generated_at="2026-01-02T00:00:00+00:00",
    )
    assert first["report_id"] != second["report_id"]
    assert first["generated_at"] != second["generated_at"]
    assert first["report_fingerprint"] == second["report_fingerprint"]
    stripped = {
        k: v for k, v in first.items() if k not in ("report_id", "generated_at")
    }
    assert stripped == {
        k: v for k, v in second.items() if k not in ("report_id", "generated_at")
    }


def test_build_report_rejects_unknown_dataset_entry() -> None:
    fixture_manifest = json.loads(
        (REPO_ROOT / "data/phase4/citations/manifest.json").read_text(encoding="utf-8")
    )
    sources_manifest = json.loads(
        (REPO_ROOT / "data/phase3/sources/manifest.json").read_text(encoding="utf-8")
    )
    dataset_manifest = {"datasets": []}
    partitions = _empty_partitions()
    with pytest.raises(ValueError, match="dataset"):
        build_report(
            partitions=partitions,
            fixture_manifest=fixture_manifest,
            dataset_manifest=dataset_manifest,
            sources_manifest=sources_manifest,
            git_commit="x",
        )
