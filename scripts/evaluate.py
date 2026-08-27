#!/usr/bin/env python3
"""Phase 3 evaluation CLI (P3-3; P3-4 adds S1 and comparison).

Usage:
    .venv/bin/python scripts/evaluate.py --dataset seed-10 --strategy s0 \
        --offline --output /tmp/phase3-s0
    .venv/bin/python scripts/evaluate.py --dataset seed-10 --strategy s1 \
        --offline --output /tmp/phase3-s1
    .venv/bin/python scripts/evaluate.py --dataset seed-10 --compare \
        --offline --output /tmp/phase3-compare

Runs the selected strategy (``s0`` single-agent or ``s1``
orchestrator-workers) over the frozen dataset in deterministic offline
mode and writes ``manifest.json``, ``cases.jsonl`` and ``summary.md``
under the caller-supplied ``--output`` directory. ``--compare`` runs
both strategies into ``<output>/s0`` and ``<output>/s1`` and writes a
``comparison.md`` table keyed by identical fingerprint fields except
strategy/prompt/config. Offline mode is the only supported mode;
results are mock quality and never claim real Provider quality.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmarks.evaluation.datasets import load_dataset_by_name  # noqa: E402
from benchmarks.evaluation.reporting import write_strategy_comparison  # noqa: E402
from benchmarks.evaluation.runner import EvaluationRunner  # noqa: E402
from benchmarks.evaluation.strategies import get_strategy  # noqa: E402


def _run_strategy(strategy_name: str, dataset, output_dir: str):
    strategy = get_strategy(strategy_name)
    runner = EvaluationRunner(strategy)
    return runner.run(dataset, output_dir=output_dir)


def _run_compare(dataset, output_dir: str) -> None:
    """Run both strategies under one output root and write comparison.md."""
    out = Path(output_dir)
    s0_dir = out / "s0"
    s1_dir = out / "s1"
    report_s0 = _run_strategy("s0", dataset, str(s0_dir))
    report_s1 = _run_strategy("s1", dataset, str(s1_dir))
    paths = write_strategy_comparison(out, report_s0, report_s1)
    print(
        f"[evaluate] comparison {report_s0.manifest.dataset_id}: "
        f"{report_s0.manifest.strategy_id} vs "
        f"{report_s1.manifest.strategy_id} "
        f"({report_s0.aggregate.total} cases each)"
    )
    print(f"[evaluate] comparison: {paths['comparison']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="evaluate.py",
        description="Run the deterministic offline Phase 3 evaluation.",
    )
    parser.add_argument(
        "--dataset", default="seed-10", help="dataset name (seed-10 or dev-40)"
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--strategy",
        default="s0",
        help="strategy id (s0 single-agent or s1 orchestrator-workers)",
    )
    selection.add_argument(
        "--compare",
        action="store_true",
        help="run both s0 and s1 into output/s0 and output/s1 and write comparison.md",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="required: deterministic offline execution (only supported mode)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="directory for manifest.json/cases.jsonl/summary.md (or the "
        "comparison output root)",
    )
    args = parser.parse_args(argv)

    if not args.offline:
        parser.error(
            "--offline is required: only deterministic offline mode is supported"
        )
        return 2

    dataset = load_dataset_by_name(args.dataset)
    try:
        if args.compare:
            _run_compare(dataset, args.output)
            return 0
        strategy = get_strategy(args.strategy)
        runner = EvaluationRunner(strategy)
        report = runner.run(dataset, output_dir=args.output)
    except ValueError as exc:
        print(f"[evaluate] error: {exc}", file=sys.stderr)
        return 2
    out = Path(args.output)

    print(
        f"[evaluate] {report.manifest.strategy_id} / {dataset.dataset_id}: "
        f"{report.aggregate.total} cases "
        f"({report.aggregate.success} success, {report.aggregate.failed} failed, "
        f"{report.aggregate.skipped} skipped)"
    )
    print(f"[evaluate] manifest: {out / 'manifest.json'}")
    print(f"[evaluate] cases:    {out / 'cases.jsonl'}")
    print(f"[evaluate] summary:  {out / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
