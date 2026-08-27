#!/usr/bin/env python3
"""P4-4 offline citation evaluation CLI (deterministic).

Usage::

    python scripts/evaluate_citations.py --dataset seed-10 --offline \\
        --output /tmp/phase4-citations-a

Guarantees:

* Deterministic: every report row and fingerprint is byte-identical across
  runs except the volatile ``report_id`` and ``generated_at`` fields.
* Offline only: ``--offline`` is required and the CLI never consults a model,
  never reads credentials, and never opens a network connection.
* Versioned data is never written: ``--output`` must point outside the
  repository's ``data/`` tree.
* Metrics consume validated records only: the fixture is loaded through the
  strict manifest contract (:func:`app.citations.contracts.load_fixture`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _bootstrap() -> None:
    """Ensure the repository root is importable when run as a script."""
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


def _format_value(value: float | None) -> str:
    if value is None:
        return "null"
    return f"{value:.6f}"


def main(argv: list[str] | None = None) -> int:
    _bootstrap()

    from app.citations import load_seed_10
    from app.citations.metrics import Pipeline, compute_partition_metrics
    from app.citations.reporting import (
        REQUIRED_PARTITION_IDS,
        build_report,
        serialize_json,
    )
    from app.citations.rules import RuleSupportChecker
    from app.citations.semantic import MOCK_ADAPTER, SemanticSupportChecker

    parser = argparse.ArgumentParser(
        prog="evaluate_citations",
        description=(
            "Deterministic offline citation evaluation (P4-4). Never "
            "consults a model and never writes into versioned data."
        ),
    )
    parser.add_argument(
        "--dataset",
        required=True,
        choices=["seed-10"],
        help="frozen Phase 4 citation dataset (only seed-10 is available)",
    )
    parser.add_argument(
        "--offline",
        required=True,
        action="store_true",
        help="deterministic offline mode (required; no model is ever consulted)",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="output directory for report.json and partitions.jsonl",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    data_root = (repo_root / "data").resolve()
    out_dir = Path(args.output).expanduser().resolve()
    if out_dir.is_relative_to(data_root):
        parser.error(
            f"refusing to write into versioned data (got {args.output}); "
            "use an output directory outside the repo"
        )

    fixture = load_seed_10()
    claims = fixture["claims"]
    citations = fixture["citations"]
    claims_by_id = {claim["claim_id"]: claim for claim in claims}
    evidence_by_id = {item["evidence_id"]: item for item in fixture["evidence"]}

    rule_checker = RuleSupportChecker()
    mock_checker = SemanticSupportChecker(adapter=MOCK_ADAPTER)
    rule_judgments = [
        rule_checker.check(
            claims_by_id[citation["claim_id"]],
            evidence_by_id[citation["evidence_id"]],
        )
        for citation in citations
    ]
    mock_judgments = [
        mock_checker.check(
            claims_by_id[citation["claim_id"]],
            evidence_by_id[citation["evidence_id"]],
        )
        for citation in citations
    ]

    rule_partition = compute_partition_metrics(
        pipeline=Pipeline.RULE,
        mode="offline",
        claims=claims,
        citations=citations,
        judgments=rule_judgments,
    )
    mock_partition = compute_partition_metrics(
        pipeline=Pipeline.SEMANTIC,
        mode="mock",
        claims=claims,
        citations=citations,
        judgments=mock_judgments,
    )
    real_partition = compute_partition_metrics(
        pipeline=Pipeline.SEMANTIC,
        mode="real",
        claims=(),
        citations=(),
        judgments=(),
        limitations=[
            "real semantic evaluation was not run: the "
            "PHASE4_REAL_SEMANTIC_SMOKE=1 opt-in is required and offline "
            "mode never consults a model"
        ],
    )

    dataset_manifest = json.loads(
        (data_root / "phase3/datasets/manifest.json").read_text(encoding="utf-8")
    )
    sources_manifest = json.loads(
        (data_root / "phase3/sources/manifest.json").read_text(encoding="utf-8")
    )
    report = build_report(
        partitions=[rule_partition, mock_partition, real_partition],
        fixture_manifest=fixture["manifest"],
        dataset_manifest=dataset_manifest,
        sources_manifest=sources_manifest,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    rows = [
        report["partitions"][partition_id] for partition_id in REQUIRED_PARTITION_IDS
    ]
    (out_dir / "partitions.jsonl").write_text(
        "".join(serialize_json(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    print(f"wrote report to {out_dir}")
    for partition_id in REQUIRED_PARTITION_IDS:
        metrics = report["partitions"][partition_id]["metrics"]
        print(
            f"  {partition_id}: "
            f"precision={_format_value(metrics['citation_precision']['value'])} "
            f"recall={_format_value(metrics['citation_recall']['value'])} "
            f"entailment={_format_value(metrics['entailment']['value'])} "
            f"unsupported_claims="
            f"{_format_value(metrics['unsupported_claim_rate']['value'])}"
        )
    print(f"report_fingerprint={report['report_fingerprint']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
