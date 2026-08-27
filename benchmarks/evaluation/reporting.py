"""Report writer for the unified evaluation runner (P3-3).

Writes exactly three files under a caller-supplied output directory:
``manifest.json`` (run fingerprint), ``cases.jsonl`` (one terminal row
per case, stable order) and ``summary.md`` (aggregate Markdown). Paths
inside reports are relative; absolute paths and secrets are never
written. The runner never writes into versioned data directories — only
the caller's output directory is touched.
"""

import json
import re
from pathlib import Path

from benchmarks.evaluation.contracts import EvaluationReport

# Versioned data root (``<repo>/data/phase3``). The runner and report
# writer never touch it: any output directory equal to or inside this
# root (after symlink resolution) is rejected so a misdirected run can
# never overwrite the frozen dataset manifest or sources.
_REPO_DATA_PHASE3 = Path(__file__).resolve().parent.parent.parent / "data" / "phase3"

# Fingerprint fields that must be byte-identical for two strategy runs
# to be comparable. Strategy/prompt/config and the volatile run
# identity (run_id/started_at) are excluded: the former differ by
# design, the latter vary per run.
_COMPARABLE_FINGERPRINT_FIELDS = (
    "dataset_id",
    "dataset_sha256",
    "corpus_id",
    "corpus_sha256",
    "model_id",
    "execution_mode",
    "runner_version",
    "git_commit",
)

_NO_WIN_NOTE = (
    "No superiority claim is made: all numbers are deterministic "
    "offline proxies and never real Provider quality."
)

# Stable redaction for any untrusted text that reaches a report:
# credentials and absolute paths (POSIX and Windows) are replaced with a
# marker. URLs are excluded by the lookbehind so legit origins survive.
_REDACTED = "[REDACTED]"
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=_-]+", re.IGNORECASE),
    re.compile(
        r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|password|"
        r"passwd|secret|token)\b\s*[:=]\s*[^\s,;]+"
    ),
)
_ABSOLUTE_PATH_PATTERNS = (
    re.compile(r"(?i)(?:[a-z]:\\|\\\\[^\\\s]+)(?:[^\\\s\"']*\\?)*"),
    re.compile(r"(?<![\w:/])(?:/[\w.~-]+)+"),
)


def redact_text(text: str) -> str:
    """Replace credentials and absolute paths with a stable marker."""
    for pattern in (*_SECRET_PATTERNS, *_ABSOLUTE_PATH_PATTERNS):
        text = pattern.sub(_REDACTED, text)
    return text


def ensure_output_dir_safe(output_dir: str | Path) -> None:
    """Reject output directories inside the versioned ``data/phase3`` root.

    The check runs on the fully resolved path (``strict=False``) so
    symlink aliases of the real data directory are caught too. Raises
    :class:`ValueError` before anything is written.
    """
    out = Path(output_dir).expanduser().resolve(strict=False)
    data_root = _REPO_DATA_PHASE3.resolve(strict=False)
    if out == data_root or data_root in out.parents:
        raise ValueError(
            f"refusing to write evaluation output into versioned data "
            f"directory {_REPO_DATA_PHASE3}: {output_dir}"
        )


def _render_latency(value: int | None) -> str:
    """Render a latency value; unavailable latency is explicit ``n/a``.

    Offline runs never measure wall-clock latency, so ``None`` must be
    rendered as unavailable — never as a fabricated ``0``.
    """
    return "n/a" if value is None else str(value)


def _render_cost(value: float | None) -> str:
    """Render a cost value; unknown cost is explicit ``n/a``.

    Unknown cost must never be invented as ``0.0``: only a measured
    value (offline mock cost ``0.0``) is rendered as a number.
    """
    return "n/a" if value is None else str(value)


def _manifest_payload(report: EvaluationReport) -> dict:
    return report.manifest.to_dict()


def _case_rows(report: EvaluationReport) -> list[dict]:
    return [case.to_dict() for case in report.cases]


def render_summary_markdown(report: EvaluationReport) -> str:
    """Deterministic Markdown summary (run_id/started_at vary per run)."""
    manifest = report.manifest
    aggregate = report.aggregate
    lines = [
        "# Evaluation Summary",
        "",
        "## Run manifest",
        "",
    ]
    manifest_fields = [
        ("run_id", manifest.run_id),
        ("runner_version", manifest.runner_version),
        ("execution_mode", manifest.execution_mode),
        ("strategy_id", manifest.strategy_id),
        ("dataset_id", manifest.dataset_id),
        ("dataset_sha256", manifest.dataset_sha256),
        ("corpus_id", manifest.corpus_id),
        ("corpus_sha256", manifest.corpus_sha256),
        ("model_id", manifest.model_id),
        ("prompt_id", manifest.prompt_id),
        ("prompt_sha256", manifest.prompt_sha256),
        ("config_sha256", manifest.config_sha256),
        ("git_commit", manifest.git_commit),
        ("git_dirty", str(manifest.git_dirty).lower()),
        ("run_fingerprint", manifest.run_fingerprint),
        ("input_fingerprint", manifest.input_fingerprint),
        ("started_at", manifest.started_at),
    ]
    for key, value in manifest_fields:
        lines.append(f"- **{key}:** `{value}`")

    lines += [
        "",
        "## Aggregate",
        "",
        "| metric | value |",
        "| --- | --- |",
        f"| total | {aggregate.total} |",
        f"| success | {aggregate.success} |",
        f"| failed | {aggregate.failed} |",
        f"| skipped | {aggregate.skipped} |",
        f"| success_rate | {aggregate.success_rate} |",
        f"| topic_recall_mean | {aggregate.topic_recall_mean} |",
        f"| source_coverage_mean | {aggregate.source_coverage_mean} |",
        f"| latency_mean_ms | {_render_latency(aggregate.latency_mean_ms)} |",
        f"| latency_median_ms | {_render_latency(aggregate.latency_median_ms)} |",
        f"| latency_max_ms | {_render_latency(aggregate.latency_max_ms)} |",
        f"| cost_total_usd | {_render_cost(aggregate.cost_total_usd)} |",
        "",
        "## Case results",
        "",
        "| case_id | status | latency_ms | tool_calls | topic_recall | "
        "source_coverage | cost_usd | error_code |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for case in report.cases:
        error_code = case.error_code if case.error_code is not None else ""
        lines.append(
            f"| {case.case_id} | {case.status} | "
            f"{_render_latency(case.latency_ms)} | "
            f"{case.tool_calls} | {case.topic_recall} | {case.source_coverage} | "
            f"{_render_cost(case.cost_usd)} | {error_code} |"
        )

    lines += ["", "## Skipped reasons", ""]
    if report.skipped_reasons:
        lines.extend(f"- {reason}" for reason in report.skipped_reasons)
    else:
        lines.append("- none")

    lines += ["", "## Limitations", ""]
    lines.extend(f"- {redact_text(limitation)}" for limitation in report.limitations)

    return "\n".join(lines) + "\n"


def write_report(output_dir: str | Path, report: EvaluationReport) -> dict[str, Path]:
    """Write manifest.json, cases.jsonl and summary.md; returns their paths.

    Only the three report files are created under ``output_dir``; nothing
    is written into versioned data directories. Directories equal to or
    inside ``data/phase3`` (including symlink aliases) are rejected
    before anything is created.
    """
    ensure_output_dir_safe(output_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    manifest_path = out / "manifest.json"
    manifest_path.write_text(
        json.dumps(_manifest_payload(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    cases_path = out / "cases.jsonl"
    cases_path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n"
            for row in _case_rows(report)
        ),
        encoding="utf-8",
    )

    summary_path = out / "summary.md"
    summary_path.write_text(render_summary_markdown(report), encoding="utf-8")

    return {
        "manifest": manifest_path,
        "cases": cases_path,
        "summary": summary_path,
    }


def _assert_comparable_fingerprints(
    report_a: EvaluationReport, report_b: EvaluationReport
) -> None:
    """Two strategy runs are comparable only on identical dataset, corpus,
    model and execution fingerprints; everything else (strategy, prompt,
    config, volatile run identity) may differ."""
    a, b = report_a.manifest, report_b.manifest
    mismatched = [
        field
        for field in _COMPARABLE_FINGERPRINT_FIELDS
        if getattr(a, field) != getattr(b, field)
    ]
    if mismatched:
        raise ValueError(
            "comparison requires identical dataset/corpus/model/execution "
            f"fingerprints; differ: {', '.join(mismatched)}"
        )
    if [case.case_id for case in report_a.cases] != [
        case.case_id for case in report_b.cases
    ]:
        raise ValueError("comparison requires identical case order in both runs")


def _strategy_name(report: EvaluationReport) -> str:
    return report.manifest.strategy_id


def render_strategy_comparison_markdown(
    report_s0: EvaluationReport, report_s1: EvaluationReport
) -> str:
    """Deterministic S0/S1 comparison table over identical frozen inputs.

    The comparison is only valid when the two runs share identical
    dataset/corpus/model/execution fingerprints (a :class:`ValueError`
    is raised otherwise); strategy, prompt, config and run identity may
    differ. Output is strictly factual: per-case and aggregate numbers,
    latency (unmeasured offline) and limitations, with an explicit note
    that no superiority claim is made. Volatile ``run_id``/``started_at``
    are never rendered so the file is byte-reproducible per fingerprint.
    """
    _assert_comparable_fingerprints(report_s0, report_s1)
    manifest_s0, manifest_s1 = report_s0.manifest, report_s1.manifest
    name_s0, name_s1 = _strategy_name(report_s0), _strategy_name(report_s1)
    aggregate_s0, aggregate_s1 = report_s0.aggregate, report_s1.aggregate

    lines = [
        "# S0 / S1 Strategy Comparison",
        "",
        "Deterministic offline comparison on identical frozen inputs.",
        "",
        "## Comparable fingerprints (identical across both runs)",
        "",
    ]
    for field in _COMPARABLE_FINGERPRINT_FIELDS:
        lines.append(f"- **{field}:** `{getattr(manifest_s0, field)}`")

    lines += [
        "",
        "## Strategy fingerprints (differ by design)",
        "",
        f"| field | {name_s0} | {name_s1} |",
        "| --- | --- | --- |",
    ]
    for field in ("strategy_id", "prompt_id", "prompt_sha256", "config_sha256"):
        lines.append(
            f"| {field} | {getattr(manifest_s0, field)} | "
            f"{getattr(manifest_s1, field)} |"
        )

    lines += [
        "",
        "## Aggregate comparison",
        "",
        f"| metric | {name_s0} | {name_s1} |",
        "| --- | --- | --- |",
    ]
    aggregate_fields = (
        ("total", aggregate_s0.total, aggregate_s1.total),
        ("success", aggregate_s0.success, aggregate_s1.success),
        ("failed", aggregate_s0.failed, aggregate_s1.failed),
        ("skipped", aggregate_s0.skipped, aggregate_s1.skipped),
        ("success_rate", aggregate_s0.success_rate, aggregate_s1.success_rate),
        (
            "topic_recall_mean",
            aggregate_s0.topic_recall_mean,
            aggregate_s1.topic_recall_mean,
        ),
        (
            "source_coverage_mean",
            aggregate_s0.source_coverage_mean,
            aggregate_s1.source_coverage_mean,
        ),
        (
            "latency_mean_ms",
            _render_latency(aggregate_s0.latency_mean_ms),
            _render_latency(aggregate_s1.latency_mean_ms),
        ),
        (
            "latency_median_ms",
            _render_latency(aggregate_s0.latency_median_ms),
            _render_latency(aggregate_s1.latency_median_ms),
        ),
        (
            "latency_max_ms",
            _render_latency(aggregate_s0.latency_max_ms),
            _render_latency(aggregate_s1.latency_max_ms),
        ),
        (
            "cost_total_usd",
            _render_cost(aggregate_s0.cost_total_usd),
            _render_cost(aggregate_s1.cost_total_usd),
        ),
    )
    for metric, value_s0, value_s1 in aggregate_fields:
        lines.append(f"| {metric} | {value_s0} | {value_s1} |")

    lines += [
        "",
        "## Case comparison",
        "",
        "| case_id | "
        f"{name_s0} status | {name_s1} status | "
        f"{name_s0} topic_recall | {name_s1} topic_recall | "
        f"{name_s0} source_coverage | {name_s1} source_coverage | "
        f"{name_s0} tool_calls | {name_s1} tool_calls | "
        f"{name_s0} latency_ms | {name_s1} latency_ms |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for case_s0, case_s1 in zip(report_s0.cases, report_s1.cases, strict=True):
        lines.append(
            f"| {case_s0.case_id} | {case_s0.status} | {case_s1.status} | "
            f"{case_s0.topic_recall} | {case_s1.topic_recall} | "
            f"{case_s0.source_coverage} | {case_s1.source_coverage} | "
            f"{case_s0.tool_calls} | {case_s1.tool_calls} | "
            f"{_render_latency(case_s0.latency_ms)} | "
            f"{_render_latency(case_s1.latency_ms)} |"
        )

    lines += ["", "## Limitations", ""]
    lines.append(f"- {name_s0}:")
    for limitation in report_s0.limitations:
        lines.append(f"  - {redact_text(limitation)}")
    lines.append(f"- {name_s1}:")
    for limitation in report_s1.limitations:
        lines.append(f"  - {redact_text(limitation)}")
    lines += ["", f"> {_NO_WIN_NOTE}"]

    return "\n".join(lines) + "\n"


def write_strategy_comparison(
    output_dir: str | Path, report_s0: EvaluationReport, report_s1: EvaluationReport
) -> dict[str, Path]:
    """Write ``comparison.md`` under the caller's output directory.

    The same versioned-data guard applies as for the per-strategy
    reports: directories equal to or inside ``data/phase3`` (including
    symlink aliases) are rejected before anything is created.
    """
    ensure_output_dir_safe(output_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    comparison_path = out / "comparison.md"
    comparison_path.write_text(
        render_strategy_comparison_markdown(report_s0, report_s1),
        encoding="utf-8",
    )
    return {"comparison": comparison_path}
