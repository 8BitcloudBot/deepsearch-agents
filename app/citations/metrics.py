"""Deterministic offline citation metrics (P4-4).

``compute_partition_metrics`` aggregates validated citation records and a
homogeneous run of judgments into four metrics, each with an explicit
numerator and denominator:

* ``citation_precision``     -- of the citations judged supported, the share
  whose curated ground truth is ``supports``: TP / judged-supported.
* ``citation_recall``        -- of the citations whose ground truth is
  ``supports``, the share judged supported: TP / truth-supported.
* ``entailment``             -- the pipeline's entailment rate: the share of
  evaluated citations the pipeline judged supported (judged-supported /
  citations).
* ``unsupported_claim_rate`` -- the share of claims with no judged-supported
  citation (unsupported claims / claims).

Guarantees (fail-closed, deterministic):

* Partitions are homogeneous: ``rule`` judgments (P4-2) are always
  ``offline``; ``semantic`` judgments (P4-3) must all carry the same declared
  mode (``mock`` or ``real``). Mixed modes, mixed judgment kinds, and
  declared-vs-actual mode mismatches raise :class:`ValueError`.
* Only validated record shapes are accepted: duplicate claim/citation ids,
  citations referencing unknown claims, and judgment counts that do not match
  the citation list raise :class:`ValueError`.
* ``unknown``, ``skipped``, ``invalid``, and ``contradicted``/``conflict``
  judgments are never counted as supported; their counts are surfaced in
  ``counts`` and partition limitations.
* A zero denominator yields ``value=None`` plus a deterministic limitation.
* Every partition carries a stable sha256 fingerprint of its canonical
  payload, so identical inputs produce byte-identical partitions.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.citations.rules import SupportJudgment, Verdict
from app.citations.semantic import (
    MOCK_ADAPTER,
    SemanticJudgment,
    SemanticState,
    canonical_sha256,
)

OFFLINE_MODE = "offline"
MOCK_MODE = "mock"
REAL_MODE = "real"

_ZERO_DENOMINATOR_LIMITATION = "{} is undefined because its denominator is zero"


class Pipeline(StrEnum):
    """The evaluation pipeline a partition belongs to (never mixed)."""

    RULE = "rule"
    SEMANTIC = "semantic"


class MetricKind(StrEnum):
    """Stable metric identifiers; part of the report contract."""

    CITATION_PRECISION = "citation_precision"
    CITATION_RECALL = "citation_recall"
    ENTAILMENT = "entailment"
    UNSUPPORTED_CLAIM_RATE = "unsupported_claim_rate"


def _fraction(numerator: int, denominator: int, *, label: str) -> MetricValue:
    """A metric value with explicit numerator/denominator (null on zero)."""
    if denominator == 0:
        return MetricValue(
            value=None,
            numerator=numerator,
            denominator=denominator,
            limitation=_ZERO_DENOMINATOR_LIMITATION.format(label),
        )
    return MetricValue(
        value=round(numerator / denominator, 6),
        numerator=numerator,
        denominator=denominator,
        limitation=None,
    )


@dataclass(frozen=True)
class MetricValue:
    """One metric: a value plus its exact numerator/denominator."""

    value: float | None
    numerator: int
    denominator: int
    limitation: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "limitation": self.limitation,
        }


@dataclass(frozen=True)
class PartitionMetrics:
    """All four metrics for one homogeneous partition, with provenance."""

    pipeline: str
    mode: str
    counts: dict[str, int]
    metrics: dict[str, MetricValue]
    limitations: tuple[str, ...]
    provenance: dict[str, Any]
    fingerprint: str

    @property
    def partition_id(self) -> str:
        return f"{self.pipeline}/{self.mode}"

    def metric(self, kind: MetricKind) -> MetricValue:
        return self.metrics[kind.value]

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline": self.pipeline,
            "mode": self.mode,
            "partition_id": self.partition_id,
            "counts": dict(sorted(self.counts.items())),
            "metrics": {
                name: value.to_dict() for name, value in sorted(self.metrics.items())
            },
            "limitations": list(self.limitations),
            "provenance": dict(sorted(self.provenance.items())),
            "fingerprint": self.fingerprint,
        }


def _reject_duplicates(
    claims: Sequence[Mapping[str, Any]],
    citations: Sequence[Mapping[str, Any]],
) -> None:
    seen_claims: set[str] = set()
    for claim in claims:
        claim_id = claim.get("claim_id")
        if claim_id in seen_claims:
            raise ValueError(f"duplicate claim id {claim_id!r}")
        seen_claims.add(claim_id)
    seen_citations: set[str] = set()
    for citation in citations:
        citation_id = citation.get("id")
        if citation_id in seen_citations:
            raise ValueError(f"duplicate citation id {citation_id!r}")
        seen_citations.add(citation_id)


def _check_links(
    claims: Sequence[Mapping[str, Any]],
    citations: Sequence[Mapping[str, Any]],
) -> None:
    claim_ids = {claim.get("claim_id") for claim in claims}
    for citation in citations:
        claim_id = citation.get("claim_id")
        if claim_id not in claim_ids:
            raise ValueError(
                f"citation {citation.get('id')!r} references unknown claim {claim_id!r}"
            )


def compute_partition_metrics(
    *,
    pipeline: Pipeline | str,
    mode: str,
    claims: Sequence[Mapping[str, Any]],
    citations: Sequence[Mapping[str, Any]],
    judgments: Sequence[Any],
    limitations: Sequence[str] = (),
) -> PartitionMetrics:
    """Aggregate one homogeneous partition of citations and judgments.

    ``judgments`` must be one :class:`SupportJudgment` (rule/offline) or
    :class:`SemanticJudgment` (semantic/mock or semantic/real) per citation,
    in citation order. Only validated record dicts are accepted.
    """
    pipe = Pipeline(pipeline)
    _reject_duplicates(claims, citations)
    _check_links(claims, citations)

    if pipe is Pipeline.RULE:
        if mode != OFFLINE_MODE:
            raise ValueError(
                "rule pipeline is deterministic and offline only; "
                f"mode must be {OFFLINE_MODE!r}, got {mode!r}"
            )
        if not all(isinstance(j, SupportJudgment) for j in judgments):
            raise ValueError("rule pipeline requires only SupportJudgment judgments")
        partition_mode = OFFLINE_MODE
    else:
        if mode not in (MOCK_MODE, REAL_MODE):
            raise ValueError(
                f"semantic pipeline mode must be {MOCK_MODE!r} or "
                f"{REAL_MODE!r}, got {mode!r}"
            )
        if not all(isinstance(j, SemanticJudgment) for j in judgments):
            raise ValueError(
                "semantic pipeline requires only SemanticJudgment judgments"
            )
        for judgment in judgments:
            if judgment.mode.value != mode:
                raise ValueError(
                    f"semantic judgment mode {judgment.mode.value!r} does not "
                    f"match partition mode {mode!r}"
                )
        partition_mode = mode

    if len(judgments) != len(citations):
        raise ValueError(
            f"got {len(judgments)} judgment(s) for {len(citations)} "
            "citation(s); judgments must be one per citation"
        )

    truth_supported = sum(
        1 for citation in citations if citation.get("support") == "supports"
    )
    judged_supported = sum(1 for judgment in judgments if judgment.supported)
    both = sum(
        1
        for judgment, citation in zip(judgments, citations)
        if judgment.supported and citation.get("support") == "supports"
    )
    if pipe is Pipeline.RULE:
        unknown_or_skipped = 0
        invalid = sum(
            1 for judgment in judgments if judgment.verdict is Verdict.INVALID
        )
    else:
        unknown_or_skipped = sum(
            1
            for judgment in judgments
            if judgment.state in (SemanticState.UNKNOWN, SemanticState.SKIPPED)
        )
        invalid = 0

    supported_claims = {
        citation.get("claim_id")
        for judgment, citation in zip(judgments, citations)
        if judgment.supported
    }
    supported_claim_count = len(supported_claims)
    unsupported_claim_count = len(claims) - supported_claim_count

    counts = {
        "claims": len(claims),
        "citations": len(citations),
        "judged_supported": judged_supported,
        "truth_supported": truth_supported,
        "both": both,
        "unknown_or_skipped": unknown_or_skipped,
        "invalid": invalid,
    }
    metrics = {
        MetricKind.CITATION_PRECISION.value: _fraction(
            both, judged_supported, label=MetricKind.CITATION_PRECISION.value
        ),
        MetricKind.CITATION_RECALL.value: _fraction(
            both, truth_supported, label=MetricKind.CITATION_RECALL.value
        ),
        MetricKind.ENTAILMENT.value: _fraction(
            judged_supported, len(citations), label=MetricKind.ENTAILMENT.value
        ),
        MetricKind.UNSUPPORTED_CLAIM_RATE.value: _fraction(
            unsupported_claim_count,
            len(claims),
            label=MetricKind.UNSUPPORTED_CLAIM_RATE.value,
        ),
    }

    partition_limitations: list[str] = list(limitations)
    if unknown_or_skipped:
        partition_limitations.append(
            f"{unknown_or_skipped} judgment(s) were unknown or skipped and "
            "are never counted as supported"
        )
    if invalid:
        partition_limitations.append(
            f"{invalid} judgment(s) were invalid and are never counted as supported"
        )
    if pipe is Pipeline.SEMANTIC and judgments:
        partition_limitations.extend(
            sorted({lim for judgment in judgments for lim in judgment.limitations})
        )
    partition_limitations = sorted(set(partition_limitations))

    if pipe is Pipeline.RULE:
        provenance: dict[str, Any] = {
            "adapter": "rule:offline",
            "model_id": None,
            "prompt_id": None,
            "prompt_sha256": None,
            "config_sha256": None,
        }
    else:
        if judgments:
            model_ids = {j.model_id for j in judgments}
            prompt_ids = {j.prompt_id for j in judgments}
            config_shas = {j.config_sha256 for j in judgments}
            if len(model_ids) != 1 or len(prompt_ids) != 1 or len(config_shas) != 1:
                raise ValueError(
                    "semantic judgments within one partition must share "
                    "model/prompt id and config fingerprint"
                )
            # prompt_sha256 varies per judgment (it fingerprints each rendered
            # prompt); aggregate them into one stable partition fingerprint.
            prompt_sha256 = canonical_sha256(
                sorted({j.prompt_sha256 for j in judgments})
            )
            model_id = next(iter(model_ids))
            prompt_id = next(iter(prompt_ids))
            config_sha256 = next(iter(config_shas))
        else:
            model_id = None
            prompt_id = None
            prompt_sha256 = None
            config_sha256 = None
        adapter = MOCK_ADAPTER if partition_mode == MOCK_MODE else "real"
        provenance = {
            "adapter": adapter,
            "model_id": model_id,
            "prompt_id": prompt_id,
            "prompt_sha256": prompt_sha256,
            "config_sha256": config_sha256,
        }

    fingerprint = canonical_sha256(
        {
            "pipeline": pipe.value,
            "mode": partition_mode,
            "counts": counts,
            "metrics": {
                name: value.to_dict() for name, value in sorted(metrics.items())
            },
            "limitations": partition_limitations,
            "provenance": provenance,
        }
    )
    return PartitionMetrics(
        pipeline=pipe.value,
        mode=partition_mode,
        counts=counts,
        metrics=metrics,
        limitations=tuple(partition_limitations),
        provenance=provenance,
        fingerprint=fingerprint,
    )


__all__ = [
    "MOCK_MODE",
    "MetricKind",
    "MetricValue",
    "OFFLINE_MODE",
    "PartitionMetrics",
    "Pipeline",
    "REAL_MODE",
    "compute_partition_metrics",
]
