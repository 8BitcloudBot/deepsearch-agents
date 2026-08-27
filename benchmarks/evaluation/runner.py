"""Unified evaluation runner (P3-3).

Orchestrates one dataset through one strategy: cases run in stable
dataset order, every case gets exactly one terminal result (success /
failed / skipped), one failure never aborts later cases, exception text
is redacted into a stable ``error_code``, and the report (manifest,
ordered case rows, aggregates) is written only under the caller's output
directory. Execution is fully offline: no network, no Provider/model
calls, ``model_id="mock:deterministic"`` and zero cost.

Fail-closed guarantees: the runner only accepts
``model_id="mock:deterministic"``; every accepted strategy output is
validated (type, case id, status, field types and ranges) inside the
per-case boundary so one bad return becomes one ``failed`` row without
affecting later cases; costs must be exactly ``0.0``; latency is
``None`` (unmeasured) rather than fabricated; and reports can never be
written into the versioned ``data/phase3`` directory. Git provenance is
mandatory: the manifest binds the current HEAD commit of this
repository, derived from ``runner.py``'s own location, and the run fails
before executing or reporting if that commit cannot be established.

Reproducibility: given the same dataset, corpus, strategy and config,
two runs produce identical case statuses, metrics and fingerprint fields
except ``run_id`` and ``started_at``; the manifest additionally binds a
boolean dirty-worktree marker and deterministic ``run_fingerprint`` /
``input_fingerprint`` values that exclude the volatile run identity.
"""

import math
import re
import statistics
import subprocess
import uuid
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path, PurePosixPath

from benchmarks.evaluation.contracts import (
    VALID_STATUSES,
    AggregateSummary,
    CaseResult,
    Dataset,
    EvaluationCase,
    EvaluationReport,
    RunManifest,
    StrategyOutput,
)
from benchmarks.evaluation.fingerprint import fingerprint
from benchmarks.evaluation.reporting import (
    ensure_output_dir_safe,
    redact_text,
    write_report,
)
from benchmarks.evaluation.source_contracts import Corpus, corpus_sha256
from benchmarks.evaluation.source_corpus import load_corpus

RUNNER_VERSION = "1.0.0"
DEFAULT_EXECUTION_MODE = "offline"
DEFAULT_MODEL_ID = "mock:deterministic"
ERROR_CODE_EXCEPTION = "strategy_error"
ERROR_CODE_INVALID_STATUS = "invalid_status"
ERROR_CODE_INVALID_OUTPUT = "invalid_strategy_output"
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

# Repository root derived from this file's own location (``<repo>/app/
# evaluation/runner.py``), so git provenance works no matter which cwd
# launches the runner or CLI.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

_GLOBAL_LIMITATION = (
    "offline deterministic run; mock results are not real Provider quality"
)


def git_worktree_dirty() -> bool:
    """True when this checkout's worktree has uncommitted changes.

    Runs ``git status --porcelain`` with cwd fixed to the repository
    root derived from ``runner.py``. Only the boolean is returned: the
    porcelain output (file names) is never stored, fingerprinted or
    written into any report. Fail-closed: an unavailable git raises
    :class:`ValueError` instead of guessing the worktree state.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"cannot determine git worktree state: {exc}") from exc
    if result.returncode != 0:
        raise ValueError("cannot determine git worktree state for provenance")
    return bool(result.stdout.strip())


@lru_cache(maxsize=1)
def git_commit_sha() -> str:
    """HEAD commit SHA of this repository; raises if unavailable.

    Runs ``git rev-parse HEAD`` with cwd fixed to the repository root
    derived from ``runner.py``, so callers launched from anywhere (e.g.
    /tmp) still get the provenance of this checkout. Fail-closed: an
    invalid or missing commit raises :class:`ValueError` instead of
    writing ``unknown`` into the manifest.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"cannot determine git HEAD commit: {exc}") from exc
    sha = result.stdout.strip()
    if result.returncode != 0 or not _GIT_SHA_RE.fullmatch(sha):
        raise ValueError("cannot determine git HEAD commit for provenance")
    return sha


def _invalid_output(reason: str) -> tuple[str, str]:
    """One stable failure pair: ``invalid_strategy_output`` + redacted reason."""
    return (ERROR_CODE_INVALID_OUTPUT, redact_text(reason))


def _valid_artifact_paths(paths) -> bool:
    """Artifact paths must be relative, non-traversing path strings."""
    if not isinstance(paths, tuple | list):
        return False
    for path in paths:
        if not isinstance(path, str) or not path:
            return False
        pure = PurePosixPath(path)
        if pure.is_absolute() or ".." in pure.parts or "\\" in path:
            return False
    return True


def _valid_latency(value) -> bool:
    """Latency is either unmeasured (None) or a non-negative int."""
    return value is None or (
        isinstance(value, int) and not isinstance(value, bool) and value >= 0
    )


def _valid_cost(value) -> bool:
    """Cost is either unknown (None) or the exact offline mock cost 0.0.

    ``None`` means the cost was not measured and must be rendered as
    JSON ``null`` / Markdown ``n/a`` — never invented as ``0.0``.
    ``NaN``/``inf``/nonzero/negative costs all fail ``== 0.0`` or the
    finiteness check, so they become a failed ``invalid_strategy_output``.
    """
    if value is None:
        return True
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and value == 0.0
    )


def _valid_count(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _valid_ratio(value) -> bool:
    """Recall/coverage must be finite and within ``[0.0, 1.0]``."""
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and 0.0 <= value <= 1.0
    )


def _valid_limitations(limitations) -> bool:
    return isinstance(limitations, tuple | list) and all(
        isinstance(lim, str) for lim in limitations
    )


def _validate_strategy_output(output, case: EvaluationCase) -> tuple[str, str] | None:
    """Validate one strategy return; ``None`` means valid.

    Returns a stable ``(error_code, redacted_limitation)`` pair for any
    malformed return so the caller can emit one ``failed`` row using the
    input case id while later cases continue.
    """
    if not isinstance(output, StrategyOutput):
        return _invalid_output("strategy returned a non-StrategyOutput value")
    if output.case_id != case.case_id:
        return _invalid_output(
            f"strategy returned case_id {output.case_id!r} for case {case.case_id!r}"
        )
    if output.status not in VALID_STATUSES:
        return (
            ERROR_CODE_INVALID_STATUS,
            redact_text(f"strategy returned unsupported status {output.status!r}"),
        )
    if not isinstance(output.answer, str):
        return _invalid_output("strategy returned a non-string answer")
    if not _valid_artifact_paths(output.artifact_paths):
        return _invalid_output("strategy returned invalid artifact_paths")
    if not _valid_latency(output.latency_ms):
        return _invalid_output("strategy returned invalid latency_ms")
    if not _valid_cost(output.cost_usd):
        return _invalid_output("strategy returned invalid cost_usd")
    if not _valid_count(output.tool_calls):
        return _invalid_output("strategy returned invalid tool_calls")
    if not _valid_ratio(output.topic_recall):
        return _invalid_output("strategy returned invalid topic_recall")
    if not _valid_ratio(output.source_coverage):
        return _invalid_output("strategy returned invalid source_coverage")
    if output.error_code is not None and (
        not isinstance(output.error_code, str) or not output.error_code
    ):
        return _invalid_output("strategy returned invalid error_code")
    if not _valid_limitations(output.limitations):
        return _invalid_output("strategy returned invalid limitations")
    return None


def _aggregate(results: tuple[CaseResult, ...]) -> AggregateSummary:
    total = len(results)
    success = sum(1 for case in results if case.status == "success")
    failed = sum(1 for case in results if case.status == "failed")
    skipped = total - success - failed
    latencies = [case.latency_ms for case in results if case.latency_ms is not None]
    known_costs = [case.cost_usd for case in results if case.cost_usd is not None]
    return AggregateSummary(
        total=total,
        success=success,
        failed=failed,
        skipped=skipped,
        success_rate=round(success / total, 4) if total else 0.0,
        topic_recall_mean=(
            round(sum(case.topic_recall for case in results) / total, 4)
            if total
            else 0.0
        ),
        source_coverage_mean=(
            round(sum(case.source_coverage for case in results) / total, 4)
            if total
            else 0.0
        ),
        # Latency is optional: offline runs do not measure wall-clock
        # latency, so unavailable latencies aggregate to None (never 0).
        latency_mean_ms=(
            round(sum(latencies) / len(latencies), 4) if latencies else None
        ),
        latency_median_ms=statistics.median(latencies) if latencies else None,
        latency_max_ms=max(latencies) if latencies else None,
        # Cost total is only meaningful when *every* case cost is known:
        # one unknown row makes the aggregate total unknown (None) — never
        # a fake 0.0, even when the other rows report the known offline
        # cost 0.0 — and an empty run has no total either.
        cost_total_usd=(
            round(sum(known_costs), 4) if total and len(known_costs) == total else None
        ),
    )


class EvaluationRunner:
    """Runs a strategy over a dataset and produces one EvaluationReport."""

    def __init__(
        self,
        strategy,
        *,
        runner_version: str = RUNNER_VERSION,
        execution_mode: str = DEFAULT_EXECUTION_MODE,
        model_id: str | None = None,
        git_commit: str | None = None,
    ):
        if execution_mode != DEFAULT_EXECUTION_MODE:
            raise ValueError(
                f"only {DEFAULT_EXECUTION_MODE!r} execution mode is supported; "
                f"got {execution_mode!r}"
            )
        self._strategy = strategy
        self._runner_version = runner_version
        self._execution_mode = execution_mode
        resolved_model = (
            model_id
            if model_id is not None
            else getattr(strategy, "model_id", DEFAULT_MODEL_ID)
        )
        if resolved_model != DEFAULT_MODEL_ID:
            raise ValueError(
                f"only {DEFAULT_MODEL_ID!r} model is supported; got {resolved_model!r}"
            )
        self._model_id = resolved_model
        if git_commit is not None and not _GIT_SHA_RE.fullmatch(git_commit):
            raise ValueError(f"invalid git_commit {git_commit!r}; must be 40 hex")
        self._git_commit = git_commit if git_commit is not None else git_commit_sha()

    def run(
        self,
        dataset: Dataset,
        corpus: Corpus | None = None,
        output_dir: str | None = None,
        run_id: str | None = None,
        started_at: str | None = None,
    ) -> EvaluationReport:
        """Execute every case in dataset order and return the report.

        ``output_dir`` is the only place files are written; ``None`` runs
        fully in memory (nothing touches the filesystem).
        """
        if corpus is None:
            corpus = load_corpus()
        if dataset.corpus_id != corpus.corpus_id:
            raise ValueError(
                f"dataset corpus {dataset.corpus_id!r} does not match "
                f"corpus {corpus.corpus_id!r}"
            )
        if output_dir is not None:
            ensure_output_dir_safe(output_dir)

        results = tuple(self._run_case(case, corpus) for case in dataset.cases)

        git_dirty = git_worktree_dirty()
        # Every manifest value is redacted *before* fingerprinting so the
        # digest can never smuggle a secret or absolute path that the
        # manifest itself would not show.
        manifest_values = {
            "run_id": redact_text(run_id or self._new_run_id()),
            "runner_version": redact_text(self._runner_version),
            "execution_mode": redact_text(self._execution_mode),
            "strategy_id": redact_text(
                getattr(self._strategy, "strategy_id", "unknown")
            ),
            "dataset_id": redact_text(dataset.dataset_id),
            "dataset_sha256": redact_text(dataset.file_sha256),
            "corpus_id": redact_text(corpus.corpus_id),
            "corpus_sha256": redact_text(corpus_sha256(corpus)),
            "model_id": redact_text(self._model_id),
            "prompt_id": redact_text(getattr(self._strategy, "prompt_id", "unknown")),
            "prompt_sha256": redact_text(
                getattr(self._strategy, "prompt_sha256", "unknown")
            ),
            "config_sha256": redact_text(
                getattr(self._strategy, "config_sha256", "unknown")
            ),
            "git_commit": redact_text(self._git_commit),
            "git_dirty": git_dirty,
            "started_at": redact_text(started_at or _utc_now()),
        }
        # Deterministic run fingerprint: every manifest field except the
        # volatile run_id/started_at (the digests themselves excluded).
        run_fingerprint = fingerprint(
            {
                key: value
                for key, value in manifest_values.items()
                if key not in ("run_id", "started_at")
            }
        )
        # Deterministic input fingerprint: exactly the frozen inputs and
        # execution identity, including the dirty-worktree marker.
        input_fingerprint = fingerprint(
            {
                field: manifest_values[field]
                for field in (
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
            }
        )

        manifest = RunManifest(
            **manifest_values,
            run_fingerprint=run_fingerprint,
            input_fingerprint=input_fingerprint,
        )

        skipped_reasons = tuple(
            f"{case.case_id}: {_skip_reason(case)}"
            for case in results
            if case.status == "skipped"
        )
        limitations = _collect_limitations(results)

        report = EvaluationReport(
            manifest=manifest,
            cases=results,
            aggregate=_aggregate(results),
            skipped_reasons=skipped_reasons,
            limitations=limitations,
        )
        if output_dir is not None:
            write_report(output_dir, report)
        return report

    def _run_case(self, case: EvaluationCase, corpus: Corpus) -> CaseResult:
        try:
            output = self._strategy.run(case, corpus)
        except Exception:
            return CaseResult(
                case_id=case.case_id,
                status="failed",
                answer="",
                error_code=ERROR_CODE_EXCEPTION,
                limitations=("strategy raised an exception; message redacted",),
            )
        invalid = _validate_strategy_output(output, case)
        if invalid is not None:
            error_code, limitation = invalid
            return CaseResult(
                case_id=case.case_id,
                status="failed",
                answer="",
                error_code=error_code,
                limitations=(limitation,),
            )
        return CaseResult(
            case_id=output.case_id,
            status=output.status,
            answer=redact_text(output.answer),
            artifact_paths=tuple(redact_text(path) for path in output.artifact_paths),
            latency_ms=output.latency_ms,
            cost_usd=output.cost_usd,
            tool_calls=output.tool_calls,
            topic_recall=output.topic_recall,
            source_coverage=output.source_coverage,
            error_code=(
                redact_text(output.error_code)
                if output.error_code is not None
                else None
            ),
            limitations=tuple(redact_text(lim) for lim in output.limitations),
        )

    def _new_run_id(self) -> str:
        return f"{self._execution_mode}-{uuid.uuid4().hex[:12]}"


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _skip_reason(case: CaseResult) -> str:
    if case.limitations:
        return case.limitations[0]
    return case.error_code or "skipped"


def _collect_limitations(results: tuple[CaseResult, ...]) -> tuple[str, ...]:
    """Global limitations: the offline invariant plus every distinct case
    limitation, in first-seen order."""
    seen: list[str] = []
    for case in results:
        for limitation in case.limitations:
            if limitation not in seen:
                seen.append(limitation)
    return (_GLOBAL_LIMITATION, *tuple(seen))
