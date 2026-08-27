"""Phase 3 evaluation contracts: frozen dataset value objects.

Case and dataset schemas are the P3-2 data contract. Cases are immutable
once a dataset version is frozen; the dataset manifest binds the file
hash, exact count and corpus identity so later phases can fingerprint a
run against exactly this data.

P3-3 adds the run-time contracts consumed by the unified runner and the
S0 strategy: :class:`StrategyOutput` (the strategy contract),
:class:`CaseResult` (one terminal row), :class:`RunManifest` (run
fingerprint), :class:`AggregateSummary` and :class:`EvaluationReport`.
"""

import re
from dataclasses import asdict, dataclass

VALID_SPLITS: frozenset[str] = frozenset({"seed", "dev"})
VALID_DIFFICULTIES: frozenset[str] = frozenset({"basic", "intermediate", "advanced"})
# e.g. ``seed-001`` or ``dev-040``; the alphabetic prefix must equal split.
CASE_ID_RE = re.compile(r"^([a-z]+)-(\d{3})$")

# Terminal case statuses; ``skipped`` is deliberately distinct from
# ``failed`` so reports can separate deliberate non-attempts from errors.
VALID_STATUSES: frozenset[str] = frozenset({"success", "failed", "skipped"})


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    split: str
    question: str
    expected_topics: tuple[str, ...]
    allowed_source_ids: tuple[str, ...]
    difficulty: str


@dataclass(frozen=True)
class Dataset:
    dataset_id: str
    schema_version: int
    corpus_id: str
    file: str
    file_sha256: str
    cases: tuple[EvaluationCase, ...]

    @property
    def case_count(self) -> int:
        return len(self.cases)


@dataclass(frozen=True)
class StrategyOutput:
    """One strategy execution: ``EvaluationStrategy.run(case, corpus)``.

    ``status`` is one of :data:`VALID_STATUSES`. ``error_code`` is a
    stable machine-readable code (never exception text). ``limitations``
    records structured caveats instead of hiding them. In offline mode
    ``model_id`` is ``mock:deterministic`` and ``cost_usd`` is ``0.0``.
    ``latency_ms`` is ``None`` when latency was not measured (the
    truthful offline default) — it is never a fabricated or wall-clock
    number. ``cost_usd`` is ``None`` when cost is *unknown* (never
    rendered as a fabricated ``0.0``); offline runs always report the
    known mock cost ``0.0``.
    """

    case_id: str
    status: str
    answer: str
    artifact_paths: tuple[str, ...] = ()
    latency_ms: int | None = None
    cost_usd: float | None = None
    tool_calls: int = 0
    topic_recall: float = 0.0
    source_coverage: float = 0.0
    error_code: str | None = None
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class CaseResult:
    """One terminal case row in a report (same schema as StrategyOutput)."""

    case_id: str
    status: str
    answer: str
    artifact_paths: tuple[str, ...] = ()
    latency_ms: int | None = None
    cost_usd: float | None = None
    tool_calls: int = 0
    topic_recall: float = 0.0
    source_coverage: float = 0.0
    error_code: str | None = None
    limitations: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CaseResult":
        return cls(
            case_id=data["case_id"],
            status=data["status"],
            answer=data["answer"],
            artifact_paths=tuple(data.get("artifact_paths", ())),
            latency_ms=data.get("latency_ms"),
            cost_usd=data.get("cost_usd"),
            tool_calls=data.get("tool_calls", 0),
            topic_recall=data.get("topic_recall", 0.0),
            source_coverage=data.get("source_coverage", 0.0),
            error_code=data.get("error_code"),
            limitations=tuple(data.get("limitations", ())),
        )


@dataclass(frozen=True)
class RunManifest:
    """Run fingerprint binding data, corpus, strategy, model, prompt,
    configuration and Git commit to every reported number.

    ``git_dirty`` marks whether the checkout worktree had uncommitted
    changes when the run started, so numbers produced from a dirty tree
    are never presented as pristine. ``run_fingerprint`` is the canonical
    SHA-256 of every other manifest field except the volatile
    ``run_id``/``started_at``; ``input_fingerprint`` is the canonical
    SHA-256 of exactly dataset/corpus/strategy/model/prompt/config/
    commit/execution-mode plus the dirty marker. Both are deterministic:
    two runs with identical inputs fingerprint identically.
    """

    run_id: str
    runner_version: str
    execution_mode: str
    strategy_id: str
    dataset_id: str
    dataset_sha256: str
    corpus_id: str
    corpus_sha256: str
    model_id: str
    prompt_id: str
    prompt_sha256: str
    config_sha256: str
    git_commit: str
    git_dirty: bool
    run_fingerprint: str
    input_fingerprint: str
    started_at: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AggregateSummary:
    """Deterministic aggregates over the ordered case results."""

    total: int
    success: int
    failed: int
    skipped: int
    success_rate: float
    topic_recall_mean: float
    source_coverage_mean: float
    latency_mean_ms: float | None
    latency_median_ms: float | None
    latency_max_ms: int | None
    cost_total_usd: float | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class EvaluationReport:
    """One complete run: manifest, ordered case results, aggregates,
    explicit skipped reasons and limitations."""

    manifest: RunManifest
    cases: tuple[CaseResult, ...]
    aggregate: AggregateSummary
    skipped_reasons: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "manifest": self.manifest.to_dict(),
            "cases": [case.to_dict() for case in self.cases],
            "aggregate": self.aggregate.to_dict(),
            "skipped_reasons": list(self.skipped_reasons),
            "limitations": list(self.limitations),
        }
