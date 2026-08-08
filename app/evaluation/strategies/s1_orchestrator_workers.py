"""S1 Orchestrator-Workers strategy: deterministic offline baseline (P3-4).

S1 mirrors S0's offline discipline but through one orchestrator and
exactly three bounded worker roles — Web snapshot (``web_snapshot``),
catalog (``catalog``) and knowledge (``knowledge``). Each worker
receives only the allowed source IDs of its own source kind, in corpus
order, and produces a bounded, deterministic summary; the orchestrator
merges the worker outputs in fixed worker order and reports the same
measured proxies as S0 (topic recall, source coverage, tool calls)
computed over the sources actually read. It never calls a Provider,
never touches the network and always reports
``model_id="mock:deterministic"`` with ``cost_usd=0.0``; numbers are
offline quality proxies and never claim real Provider quality. Offline
latency is never measured or fabricated: ``latency_ms`` is ``None`` for
the strategy and every worker.

Worker contract: each worker output carries ``worker_id``, ordered
``source_ids``, ``summary``, ``latency_ms`` and ``status``. A worker
with no allowed sources of its kind is ``skipped``; a worker that raises
becomes a structured ``failed`` limitation (exception text redacted)
without aborting the remaining workers or the case.

Fail-closed worker boundary: every worker return is validated inside the
per-worker exception boundary. A success output may name only the exact
ordered source IDs passed to that worker; skipped/failed outputs may not
claim source IDs; ``worker_id`` must match the role; offline
``latency_ms`` must be ``None``; status must be ``success``/``skipped``/
``failed``; and summary, error_code, limitations and tuple contents must
have their declared types. A malformed return becomes one structured
``failed`` WorkerOutput with the stable ``invalid_worker_output`` error
code and a redacted limitation — it never contaminates answer metrics
and never aborts the remaining workers or later cases. The worker
topology is also validated fail-closed at strategy construction: exactly
the three unique ``WORKER_ROLES`` in fixed order, each with ``kind``
matching its ``worker_id``.

Determinism contract: identical (case, corpus) input yields identical
outputs, so two offline runs fingerprint identically.
"""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Literal

from app.evaluation.contracts import EvaluationCase, StrategyOutput
from app.research.contracts import Corpus, SourceKind, SourceRecord

STRATEGY_ID = "s1-orchestrator-workers"
MODEL_ID = "mock:deterministic"
PROMPT_ID = "s1-orchestrator-workers-v1"

# Exactly three worker roles, in the fixed merge order.
WORKER_ROLES: tuple[Literal["web_snapshot", "catalog", "knowledge"], ...] = (
    "web_snapshot",
    "catalog",
    "knowledge",
)

# Display roles for the answer (worker_id == source kind).
_ROLE_LABELS: dict[str, str] = {
    "web_snapshot": "Web snapshot",
    "catalog": "Catalog",
    "knowledge": "Knowledge",
}

S1_SYSTEM_PROMPT = (
    "You are S1, a deterministic offline orchestrator with three bounded "
    "workers (Web snapshot, catalog, knowledge). Dispatch each allowed "
    "source to exactly one worker by source kind, merge the worker "
    "outputs in fixed worker order, answer the question from that "
    "material only and report measured topic recall and source "
    "coverage. Never claim real Provider quality: this run is an "
    "offline mock baseline."
)

# Deterministic offline configuration; its canonical hash is part of the
# run fingerprint so config changes invalidate old numbers.
S1_CONFIG = {
    "mode": "offline-deterministic",
    "max_source_chars": 4000,
    "worker_roles": list(WORKER_ROLES),
    "merge_order": "fixed-worker-role-order",
    "topic_match": "case-insensitive-normalized-substring",
}

_MAX_SOURCE_CHARS = S1_CONFIG["max_source_chars"]

# Normalize text for topic matching: lowercase and collapse any run of
# non-alphanumerics to a single space so ``topic-recall`` matches
# ``Topic recall`` deterministically (same rule as S0).
_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")

_OFFLINE_LIMITATION = "deterministic offline proxy; not a real Provider quality claim"

# Stable error code for malformed worker returns (never exception text).
ERROR_CODE_INVALID_WORKER_OUTPUT = "invalid_worker_output"

_VALID_WORKER_STATUSES: frozenset[str] = frozenset({"success", "skipped", "failed"})


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_hash(payload: dict) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return _sha256(canonical)


def _normalize(text: str) -> str:
    return _NORMALIZE_RE.sub(" ", text.lower()).strip()


@dataclass(frozen=True)
class WorkerOutput:
    """One bounded worker's deterministic result.

    ``source_ids`` are ordered by corpus order; ``status`` is
    ``success`` / ``skipped`` / ``failed``. Offline ``latency_ms`` is
    always ``None`` (unmeasured). ``error_code`` is stable and machine
    readable; limitations never carry exception text.
    """

    worker_id: str
    source_ids: tuple[str, ...]
    summary: str
    latency_ms: int | None = None
    status: str = "success"
    error_code: str | None = None
    limitations: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "WorkerOutput":
        return cls(
            worker_id=data["worker_id"],
            source_ids=tuple(data.get("source_ids", ())),
            summary=data.get("summary", ""),
            latency_ms=data.get("latency_ms"),
            status=data.get("status", "success"),
            error_code=data.get("error_code"),
            limitations=tuple(data.get("limitations", ())),
        )


class DeterministicWorker:
    """One bounded worker: summarises only its own source kind.

    Bounded in both directions: it only ever sees the allowed sources of
    one kind (the orchestrator filters before calling), and it truncates
    each source's content to ``max_source_chars``. With no sources of its
    kind it reports ``skipped`` instead of failing.
    """

    def __init__(
        self,
        worker_id: str,
        kind: SourceKind,
        role: str,
        max_source_chars: int,
    ):
        self.worker_id = worker_id
        self.kind = kind
        self.role = role
        self.max_source_chars = max_source_chars

    def run(self, sources: tuple[SourceRecord, ...]) -> WorkerOutput:
        if not sources:
            return WorkerOutput(
                worker_id=self.worker_id,
                source_ids=(),
                summary="",
                status="skipped",
                error_code="no_sources_of_kind",
                limitations=(
                    f"worker {self.worker_id} skipped: no allowed "
                    f"{self.worker_id} sources for this case",
                ),
            )

        excerpts: list[str] = []
        for source in sources:
            content = source.content
            if len(content) > self.max_source_chars:
                content = content[: self.max_source_chars] + "\n\n[TRUNCATED]\n"
            excerpts.append(f"### {source.source_id}\n{content}")
        return WorkerOutput(
            worker_id=self.worker_id,
            source_ids=tuple(source.source_id for source in sources),
            summary="\n".join(excerpts),
            # Offline latency is never measured or fabricated.
            latency_ms=None,
            status="success",
        )


def _default_workers() -> tuple[DeterministicWorker, ...]:
    return tuple(
        DeterministicWorker(
            worker_id=worker_id,
            kind=worker_id,
            role=_ROLE_LABELS[worker_id],
            max_source_chars=_MAX_SOURCE_CHARS,
        )
        for worker_id in WORKER_ROLES
    )


# The default three bounded workers in the fixed merge order.
DEFAULT_WORKERS: tuple[DeterministicWorker, ...] = _default_workers()


def _validate_worker_topology(workers) -> None:
    """Fail closed: exactly the three unique WORKER_ROLES in fixed order,
    each with ``kind`` matching its ``worker_id``. Raises ValueError."""
    if not isinstance(workers, tuple | list):
        raise ValueError("S1 requires exactly 3 workers in the fixed role order")
    ids = tuple(getattr(worker, "worker_id", None) for worker in workers)
    if len(ids) != len(WORKER_ROLES):
        raise ValueError(f"S1 requires exactly 3 workers; got {len(ids)} workers")
    if ids != WORKER_ROLES:
        raise ValueError(
            "S1 workers must be exactly the three WORKER_ROLES in fixed "
            f"role order; got {ids!r}"
        )
    for worker in workers:
        if getattr(worker, "kind", None) != worker.worker_id:
            raise ValueError(
                f"S1 worker {worker.worker_id!r} kind must match worker_id"
            )


def _validate_worker_output(output, worker: DeterministicWorker, sources) -> str | None:
    """Validate one worker return against the bounded-worker contract.

    Returns ``None`` when valid, else a stable reason string. Reasons are
    static text that never embeds raw return values, so they are safe to
    surface (redacted) in a limitation.
    """
    if not isinstance(output, WorkerOutput):
        return "worker returned a non-WorkerOutput value"
    if output.worker_id != worker.worker_id:
        return "worker_id does not match the worker role"
    if output.status not in _VALID_WORKER_STATUSES:
        return "unsupported worker status"
    # Offline latency is never measured or fabricated: it must stay None.
    if output.latency_ms is not None:
        return "fabricated latency (offline workers must report None)"
    if not isinstance(output.source_ids, tuple) or not all(
        isinstance(source_id, str) for source_id in output.source_ids
    ):
        return "source_ids must be a tuple of strings"
    if output.status == "success":
        expected = tuple(source.source_id for source in sources)
        if output.source_ids != expected:
            return (
                "source_ids must be exactly the ordered source IDs passed to the worker"
            )
    elif output.source_ids:
        return "skipped or failed workers may not claim source_ids"
    if not isinstance(output.summary, str):
        return "summary must be a string"
    if output.error_code is not None and (
        not isinstance(output.error_code, str) or not output.error_code
    ):
        return "error_code must be a non-empty string"
    if not isinstance(output.limitations, tuple) or not all(
        isinstance(limitation, str) for limitation in output.limitations
    ):
        return "limitations must be a tuple of strings"
    return None


@dataclass(frozen=True)
class S1OrchestratorWorkersStrategy:
    """S1: deterministic orchestrator over three bounded workers."""

    strategy_id: str = STRATEGY_ID
    model_id: str = MODEL_ID
    prompt_id: str = PROMPT_ID
    prompt_sha256: str = _sha256(S1_SYSTEM_PROMPT)
    config_sha256: str = _canonical_hash(S1_CONFIG)
    workers: tuple[DeterministicWorker, ...] = DEFAULT_WORKERS

    def __post_init__(self) -> None:
        # Fail closed at construction: only the fixed three-role topology
        # with matching kinds may ever run.
        _validate_worker_topology(self.workers)

    @property
    def _effective_workers(self) -> tuple[DeterministicWorker, ...]:
        # An explicit worker override (tests of the failure boundary)
        # replaces the defaults; otherwise exactly the three fixed roles.
        return self.workers if self.workers else _default_workers()

    def run_workers(
        self, case: EvaluationCase, corpus: Corpus
    ) -> tuple[WorkerOutput, ...]:
        """Run every worker on its own kind's allowed sources, in fixed
        worker order. A raising worker becomes one ``failed`` WorkerOutput
        and never aborts the remaining workers."""
        allowed = [
            source
            for source in corpus.sources
            if source.source_id in case.allowed_source_ids
        ]
        by_kind: dict[str, list[SourceRecord]] = {}
        for source in allowed:
            by_kind.setdefault(source.kind, []).append(source)
        return tuple(
            self._run_worker(worker, tuple(by_kind.get(worker.kind, ())))
            for worker in self._effective_workers
        )

    def _run_worker(
        self, worker: DeterministicWorker, sources: tuple[SourceRecord, ...]
    ) -> WorkerOutput:
        try:
            output = worker.run(sources)
        except Exception:
            return WorkerOutput(
                worker_id=worker.worker_id,
                source_ids=(),
                summary="",
                status="failed",
                error_code="worker_error",
                limitations=(
                    f"worker {worker.worker_id} failed: worker raised an "
                    "exception; message redacted",
                ),
            )
        # Validate inside the per-worker exception boundary: a malformed
        # return becomes one structured failed output and never aborts the
        # remaining workers or the case.
        reason = _validate_worker_output(output, worker, sources)
        if reason is None:
            return output
        return WorkerOutput(
            worker_id=worker.worker_id,
            source_ids=(),
            summary="",
            status="failed",
            error_code=ERROR_CODE_INVALID_WORKER_OUTPUT,
            limitations=(
                f"worker {worker.worker_id} failed: invalid worker output "
                f"({reason}); details redacted",
            ),
        )

    def run(self, case: EvaluationCase, corpus: Corpus) -> StrategyOutput:
        if not case.allowed_source_ids:
            return StrategyOutput(
                case_id=case.case_id,
                status="skipped",
                answer="",
                error_code="no_allowed_sources",
                limitations=("no allowed sources present in the corpus",),
            )

        workers = self._effective_workers
        worker_outputs = self.run_workers(case, corpus)
        # Key by the expected role, not by the (untrusted) return value.
        by_id = {
            worker.worker_id: output for worker, output in zip(workers, worker_outputs)
        }

        # Fixed merge: worker order is the declared role order, and each
        # worker's source_ids are already in corpus order.
        used_ids: list[str] = []
        for worker in workers:
            used_ids.extend(by_id[worker.worker_id].source_ids)
        successful = [
            by_id[worker.worker_id]
            for worker in workers
            if by_id[worker.worker_id].status == "success"
        ]

        combined = "\n".join(output.summary for output in successful)
        normalized = _normalize(combined)
        matched = [
            topic for topic in case.expected_topics if _normalize(topic) in normalized
        ]
        topic_recall = round(len(matched) / len(case.expected_topics), 4)
        source_coverage = round(len(used_ids) / len(case.allowed_source_ids), 4)
        tool_calls = len(used_ids)

        answer = self._render_answer(
            case,
            corpus,
            workers,
            by_id,
            topic_recall,
            matched,
            source_coverage,
            tool_calls,
        )

        limitations: list[str] = [_OFFLINE_LIMITATION]
        for worker in workers:
            output = by_id[worker.worker_id]
            for limitation in output.limitations:
                if limitation not in limitations:
                    limitations.append(limitation)

        if not successful:
            return StrategyOutput(
                case_id=case.case_id,
                status="failed",
                answer=answer,
                latency_ms=None,
                cost_usd=0.0,
                tool_calls=tool_calls,
                topic_recall=topic_recall,
                source_coverage=source_coverage,
                error_code="all_workers_failed",
                limitations=tuple(limitations),
            )

        return StrategyOutput(
            case_id=case.case_id,
            status="success",
            answer=answer,
            # No wall-clock measurement offline: latency stays None so
            # reports render it as unavailable instead of a fabricated ms.
            latency_ms=None,
            cost_usd=0.0,
            tool_calls=tool_calls,
            topic_recall=topic_recall,
            source_coverage=source_coverage,
            limitations=tuple(limitations),
        )

    def _render_answer(
        self,
        case: EvaluationCase,
        corpus: Corpus,
        workers: tuple[DeterministicWorker, ...],
        by_id: dict[str, WorkerOutput],
        topic_recall: float,
        matched: list[str],
        source_coverage: float,
        tool_calls: int,
    ) -> str:
        answer_lines = [
            "# S1 Orchestrator-Workers Answer",
            "",
            f"**Case:** {case.case_id}",
            f"**Question:** {case.question}",
            "**Execution mode:** offline (deterministic)",
            f"**Model:** {MODEL_ID}",
            f"**Corpus:** {corpus.corpus_id}",
            "",
            "## Worker boundaries",
        ]
        for worker in workers:
            output = by_id[worker.worker_id]
            sources = ", ".join(output.source_ids) if output.source_ids else "none"
            answer_lines.append(
                f"- {worker.worker_id} ({worker.role}): "
                f"status={output.status}, source_ids=[{sources}]"
            )
        answer_lines.append("")
        answer_lines.append("## Worker summaries")
        for worker in workers:
            output = by_id[worker.worker_id]
            answer_lines.append("")
            answer_lines.append(f"### {worker.worker_id} ({worker.role})")
            answer_lines.append(f"**Status:** {output.status}")
            if output.source_ids:
                answer_lines.append(
                    f"**Sources (corpus order):** {', '.join(output.source_ids)}"
                )
            if output.summary:
                answer_lines.append(output.summary)
            for limitation in output.limitations:
                answer_lines.append(f"**Note:** {limitation}")
        answer_lines.append("")
        answer_lines.append("## Measured metrics")
        answer_lines.append(
            f"- topic_recall={topic_recall} "
            f"({len(matched)}/{len(case.expected_topics)} "
            f"matched: {', '.join(matched) if matched else 'none'})"
        )
        answer_lines.append(f"- source_coverage={source_coverage}")
        answer_lines.append(f"- tool_calls={tool_calls}")
        answer_lines.append("- cost_usd=0.0 (offline mock)")
        return "\n".join(answer_lines) + "\n"
