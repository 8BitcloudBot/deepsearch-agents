"""Unit tests for deterministic citation metrics (P4-4).

The metrics layer consumes validated records only and aggregates judgments
strictly per homogeneous pipeline (rule/offline, semantic/mock,
semantic/real). Unknown/skipped/conflict judgments are never counted as
supported, duplicate ids are rejected, mixed modes are rejected, and a zero
denominator yields a ``null`` value plus a deterministic limitation.
"""

from __future__ import annotations

import json

import pytest

from app.citations.metrics import (
    MetricKind,
    MetricValue,
    PartitionMetrics,
    Pipeline,
    compute_partition_metrics,
)
from app.citations.rules import SupportJudgment, Verdict
from app.citations.semantic import (
    MOCK_ADAPTER,
    SemanticJudgment,
    SemanticMode,
    SemanticState,
)

WEB_HASH = (
    "794bed8459aca36698d8fe6bb2b749c"  # pragma: allowlist secret
    "0ff003d0e36ff629cbae51536f314ddeb"  # pragma: allowlist secret
)


def make_claim(claim_id: str, statement: str = "some statement") -> dict:
    return {"type": "claim", "claim_id": claim_id, "statement": statement}


def make_evidence(evidence_id: str, quote: str = "some quote") -> dict:
    return {
        "type": "evidence",
        "evidence_id": evidence_id,
        "source_id": "web-agent-frameworks-v1",
        "source_kind": "web_snapshot",
        "content_sha256": WEB_HASH,
        "locator": {"kind": "anchor", "value": evidence_id},
        "quote": quote,
    }


def make_citation(
    cite_id: str,
    claim_id: str,
    evidence_id: str,
    *,
    support: str = "supports",
) -> dict:
    return {
        "type": "citation",
        "id": cite_id,
        "claim_id": claim_id,
        "evidence_id": evidence_id,
        "support": support,
        "conflict": "none",
        "version": "1.0.0",
    }


def rule_judgment(
    *,
    supported: bool,
    verdict: Verdict = Verdict.SUPPORTED,
    fp: str | None = None,
) -> SupportJudgment:
    if fp is None:
        fp = f"rule-{verdict.value}-{int(supported)}"
    return SupportJudgment(
        supported=supported,
        verdict=verdict,
        score=1.0 if supported else 0.0,
        matched_tokens=(),
        rules=(),
        reasons=(),
        fingerprint=fp,
    )


def semantic_judgment(
    state: SemanticState,
    mode: SemanticMode = SemanticMode.MOCK,
) -> SemanticJudgment:
    return SemanticJudgment(
        state=state,
        supported=state is SemanticState.SUPPORTED,
        mode=mode,
        model_id=MOCK_ADAPTER if mode is SemanticMode.MOCK else "real:test-model",
        prompt_id="p4-semantic-support-v1",
        prompt_sha256="prompt-hash",
        config_sha256="config-hash",
        reasons=(),
        limitations=(),
        fingerprint=f"semantic-{mode.value}-{state.value}",
    )


def metric(partition: PartitionMetrics, kind: MetricKind) -> MetricValue:
    return partition.metrics[kind.value]


def assert_metric(
    partition: PartitionMetrics,
    kind: MetricKind,
    value: float | None,
    numerator: int,
    denominator: int,
) -> None:
    got = metric(partition, kind)
    assert got.value == value
    assert got.numerator == numerator
    assert got.denominator == denominator


# -- denominators and values ------------------------------------------------


def test_rule_partition_denominators_and_values() -> None:
    claims = [make_claim(f"c{i}") for i in range(1, 6)]
    citations = [
        make_citation("cite-1", "c1", "ev-1"),  # truth supports, judged supported
        make_citation("cite-2", "c2", "ev-2"),  # truth supports, judged supported
        make_citation("cite-3", "c3", "ev-3"),  # truth supports, judged NOT supported
        make_citation("cite-4", "c4", "ev-4", support="neutral"),  # judged supported
        make_citation("cite-5", "c5", "ev-5", support="contradicts"),  # judged NOT
    ]
    judgments = [
        rule_judgment(supported=True),
        rule_judgment(supported=True),
        rule_judgment(supported=False),
        rule_judgment(supported=True),
        rule_judgment(supported=False),
    ]
    partition = compute_partition_metrics(
        pipeline=Pipeline.RULE,
        mode="offline",
        claims=claims,
        citations=citations,
        judgments=judgments,
    )
    assert partition.pipeline == "rule"
    assert partition.mode == "offline"
    assert partition.counts == {
        "claims": 5,
        "citations": 5,
        "judged_supported": 3,
        "truth_supported": 3,
        "both": 2,
        "unknown_or_skipped": 0,
        "invalid": 0,
    }
    assert_metric(partition, MetricKind.CITATION_PRECISION, round(2 / 3, 6), 2, 3)
    assert_metric(partition, MetricKind.CITATION_RECALL, round(2 / 3, 6), 2, 3)
    assert_metric(partition, MetricKind.ENTAILMENT, 3 / 5, 3, 5)
    assert_metric(partition, MetricKind.UNSUPPORTED_CLAIM_RATE, 2 / 5, 2, 5)


def test_claim_is_supported_when_any_citation_supports() -> None:
    claims = [make_claim("c6"), make_claim("c7")]
    citations = [
        make_citation("cite-6a", "c6", "ev-6a"),
        make_citation("cite-6b", "c6", "ev-6b"),
        make_citation("cite-7a", "c7", "ev-7a"),
        make_citation("cite-7b", "c7", "ev-7b"),
    ]
    judgments = [
        rule_judgment(supported=False),
        rule_judgment(supported=False),
        rule_judgment(supported=False),
        rule_judgment(supported=True),
    ]
    partition = compute_partition_metrics(
        pipeline=Pipeline.RULE,
        mode="offline",
        claims=claims,
        citations=citations,
        judgments=judgments,
    )
    # claim c7 is supported by cite-7b; c6 has no supporting citation.
    assert_metric(partition, MetricKind.UNSUPPORTED_CLAIM_RATE, 0.5, 1, 2)
    assert_metric(partition, MetricKind.CITATION_PRECISION, 1.0, 1, 1)


# -- duplicates and integrity -------------------------------------------------


def test_duplicate_citation_id_rejected() -> None:
    claims = [make_claim("c1")]
    citations = [
        make_citation("cite-1", "c1", "ev-1"),
        make_citation("cite-1", "c1", "ev-2"),
    ]
    judgments = [rule_judgment(supported=True), rule_judgment(supported=True)]
    with pytest.raises(ValueError, match="duplicate citation"):
        compute_partition_metrics(
            pipeline=Pipeline.RULE,
            mode="offline",
            claims=claims,
            citations=citations,
            judgments=judgments,
        )


def test_duplicate_claim_id_rejected() -> None:
    claims = [make_claim("c1"), make_claim("c1")]
    citations = [make_citation("cite-1", "c1", "ev-1")]
    judgments = [rule_judgment(supported=True)]
    with pytest.raises(ValueError, match="duplicate claim"):
        compute_partition_metrics(
            pipeline=Pipeline.RULE,
            mode="offline",
            claims=claims,
            citations=citations,
            judgments=judgments,
        )


def test_citation_referencing_unknown_claim_rejected() -> None:
    claims = [make_claim("c1")]
    citations = [make_citation("cite-1", "c-missing", "ev-1")]
    judgments = [rule_judgment(supported=True)]
    with pytest.raises(ValueError, match="unknown claim"):
        compute_partition_metrics(
            pipeline=Pipeline.RULE,
            mode="offline",
            claims=claims,
            citations=citations,
            judgments=judgments,
        )


def test_judgment_count_must_match_citations() -> None:
    claims = [make_claim("c1")]
    citations = [make_citation("cite-1", "c1", "ev-1")]
    with pytest.raises(ValueError, match="judgments"):
        compute_partition_metrics(
            pipeline=Pipeline.RULE,
            mode="offline",
            claims=claims,
            citations=citations,
            judgments=[],
        )


# -- unknown / skipped / conflict are never supported ------------------------


def test_unknown_and_skipped_never_counted_as_supported() -> None:
    claims = [make_claim(f"c{i}") for i in range(1, 5)]
    citations = [
        make_citation("cite-1", "c1", "ev-1"),
        make_citation("cite-2", "c2", "ev-2"),
        make_citation("cite-3", "c3", "ev-3"),
        make_citation("cite-4", "c4", "ev-4", support="neutral"),
    ]
    judgments = [
        semantic_judgment(SemanticState.SUPPORTED),
        semantic_judgment(SemanticState.UNKNOWN),
        semantic_judgment(SemanticState.SKIPPED),
        semantic_judgment(SemanticState.UNSUPPORTED),
    ]
    partition = compute_partition_metrics(
        pipeline=Pipeline.SEMANTIC,
        mode="mock",
        claims=claims,
        citations=citations,
        judgments=judgments,
    )
    assert partition.counts["judged_supported"] == 1
    assert partition.counts["unknown_or_skipped"] == 2
    assert partition.counts["both"] == 1
    assert partition.counts["truth_supported"] == 3
    assert_metric(partition, MetricKind.CITATION_PRECISION, 1.0, 1, 1)
    assert_metric(partition, MetricKind.CITATION_RECALL, round(1 / 3, 6), 1, 3)
    assert_metric(partition, MetricKind.ENTAILMENT, 0.25, 1, 4)


def test_contradicted_and_conflict_never_counted_as_supported() -> None:
    claims = [make_claim(f"c{i}") for i in range(1, 4)]
    citations = [
        make_citation("cite-1", "c1", "ev-1"),
        make_citation("cite-2", "c2", "ev-2"),
        make_citation("cite-3", "c3", "ev-3"),
    ]
    judgments = [
        rule_judgment(
            supported=False,
            verdict=Verdict.CONTRADICTED,
            fp="rule-contradicted-0",
        ),
        rule_judgment(supported=False, verdict=Verdict.INVALID, fp="rule-invalid-0"),
        rule_judgment(supported=True, verdict=Verdict.SUPPORTED, fp="rule-supported-1"),
    ]
    partition = compute_partition_metrics(
        pipeline=Pipeline.RULE,
        mode="offline",
        claims=claims,
        citations=citations,
        judgments=judgments,
    )
    assert partition.counts["judged_supported"] == 1
    assert partition.counts["invalid"] == 1
    assert_metric(partition, MetricKind.CITATION_PRECISION, 1.0, 1, 1)

    semantic_judgments = [
        semantic_judgment(SemanticState.CONFLICT),
        semantic_judgment(SemanticState.SUPPORTED),
    ]
    semantic_partition = compute_partition_metrics(
        pipeline=Pipeline.SEMANTIC,
        mode="mock",
        claims=[make_claim("c1"), make_claim("c2")],
        citations=[
            make_citation("cite-1", "c1", "ev-1"),
            make_citation("cite-2", "c2", "ev-2"),
        ],
        judgments=semantic_judgments,
    )
    assert semantic_partition.counts["judged_supported"] == 1


# -- homogeneity --------------------------------------------------------------


def test_mixed_semantic_modes_rejected() -> None:
    claims = [make_claim("c1"), make_claim("c2")]
    citations = [
        make_citation("cite-1", "c1", "ev-1"),
        make_citation("cite-2", "c2", "ev-2"),
    ]
    judgments = [
        semantic_judgment(SemanticState.SUPPORTED, SemanticMode.MOCK),
        semantic_judgment(SemanticState.SUPPORTED, SemanticMode.REAL),
    ]
    with pytest.raises(ValueError, match="mode"):
        compute_partition_metrics(
            pipeline=Pipeline.SEMANTIC,
            mode="mock",
            claims=claims,
            citations=citations,
            judgments=judgments,
        )


def test_mixed_judgment_kinds_rejected() -> None:
    claims = [make_claim("c1"), make_claim("c2")]
    citations = [
        make_citation("cite-1", "c1", "ev-1"),
        make_citation("cite-2", "c2", "ev-2"),
    ]
    judgments = [
        rule_judgment(supported=True),
        semantic_judgment(SemanticState.SUPPORTED),
    ]
    with pytest.raises(ValueError, match="judgment"):
        compute_partition_metrics(
            pipeline=Pipeline.SEMANTIC,
            mode="mock",
            claims=claims,
            citations=citations,
            judgments=judgments,
        )


def test_semantic_mode_mismatch_rejected() -> None:
    claims = [make_claim("c1")]
    citations = [make_citation("cite-1", "c1", "ev-1")]
    judgments = [semantic_judgment(SemanticState.SUPPORTED, SemanticMode.REAL)]
    with pytest.raises(ValueError, match="mode"):
        compute_partition_metrics(
            pipeline=Pipeline.SEMANTIC,
            mode="mock",
            claims=claims,
            citations=citations,
            judgments=judgments,
        )


def test_rule_mode_must_be_offline() -> None:
    claims = [make_claim("c1")]
    citations = [make_citation("cite-1", "c1", "ev-1")]
    judgments = [rule_judgment(supported=True)]
    with pytest.raises(ValueError, match="offline"):
        compute_partition_metrics(
            pipeline=Pipeline.RULE,
            mode="real",
            claims=claims,
            citations=citations,
            judgments=judgments,
        )


# -- null division ------------------------------------------------------------


def test_zero_denominator_yields_null_with_limitation() -> None:
    claims = [make_claim("c1"), make_claim("c2")]
    citations = [
        make_citation("cite-1", "c1", "ev-1"),
        make_citation("cite-2", "c2", "ev-2"),
    ]
    judgments = [
        rule_judgment(supported=False),
        rule_judgment(supported=False),
    ]
    partition = compute_partition_metrics(
        pipeline=Pipeline.RULE,
        mode="offline",
        claims=claims,
        citations=citations,
        judgments=judgments,
    )
    precision = metric(partition, MetricKind.CITATION_PRECISION)
    assert precision.value is None
    assert precision.numerator == 0
    assert precision.denominator == 0
    assert precision.limitation
    assert_metric(partition, MetricKind.CITATION_RECALL, 0.0, 0, 2)
    assert_metric(partition, MetricKind.ENTAILMENT, 0.0, 0, 2)
    assert_metric(partition, MetricKind.UNSUPPORTED_CLAIM_RATE, 1.0, 2, 2)


def test_empty_inputs_yield_all_null_metrics() -> None:
    partition = compute_partition_metrics(
        pipeline=Pipeline.SEMANTIC,
        mode="real",
        claims=(),
        citations=(),
        judgments=(),
    )
    assert partition.counts["claims"] == 0
    assert partition.counts["citations"] == 0
    for kind in MetricKind:
        mv = metric(partition, kind)
        assert mv.value is None
        assert mv.numerator == 0
        assert mv.denominator == 0
        assert mv.limitation


def test_real_skipped_partition_metrics() -> None:
    claims = [make_claim(f"c{i}") for i in range(1, 4)]
    citations = [make_citation(f"cite-{i}", f"c{i}", f"ev-{i}") for i in range(1, 4)]
    judgments = [
        semantic_judgment(SemanticState.SKIPPED, SemanticMode.REAL) for _ in range(3)
    ]
    partition = compute_partition_metrics(
        pipeline=Pipeline.SEMANTIC,
        mode="real",
        claims=claims,
        citations=citations,
        judgments=judgments,
    )
    assert partition.mode == "real"
    assert partition.counts["unknown_or_skipped"] == 3
    precision = metric(partition, MetricKind.CITATION_PRECISION)
    assert precision.value is None
    assert precision.denominator == 0
    assert_metric(partition, MetricKind.CITATION_RECALL, 0.0, 0, 3)
    assert_metric(partition, MetricKind.ENTAILMENT, 0.0, 0, 3)
    assert_metric(partition, MetricKind.UNSUPPORTED_CLAIM_RATE, 1.0, 3, 3)


# -- fingerprints and provenance ----------------------------------------------


def test_fingerprint_stable_and_sensitive() -> None:
    claims = [make_claim("c1"), make_claim("c2")]
    citations = [
        make_citation("cite-1", "c1", "ev-1"),
        make_citation("cite-2", "c2", "ev-2"),
    ]
    judgments = [rule_judgment(supported=True), rule_judgment(supported=False)]

    def compute(judgments: list[SupportJudgment]) -> PartitionMetrics:
        return compute_partition_metrics(
            pipeline=Pipeline.RULE,
            mode="offline",
            claims=claims,
            citations=citations,
            judgments=judgments,
        )

    first = compute(list(judgments))
    second = compute(list(judgments))
    assert first.fingerprint == second.fingerprint
    flipped = [
        rule_judgment(supported=True, fp="rule-supported-1"),
        rule_judgment(supported=True, fp="rule-supported-1"),
    ]
    assert compute(flipped).fingerprint != first.fingerprint


def test_semantic_provenance_carries_fingerprints() -> None:
    claims = [make_claim("c1")]
    citations = [make_citation("cite-1", "c1", "ev-1")]
    judgments = [semantic_judgment(SemanticState.SUPPORTED, SemanticMode.MOCK)]
    partition = compute_partition_metrics(
        pipeline=Pipeline.SEMANTIC,
        mode="mock",
        claims=claims,
        citations=citations,
        judgments=judgments,
    )
    prov = partition.provenance
    assert prov["model_id"] == MOCK_ADAPTER
    assert prov["prompt_id"] == "p4-semantic-support-v1"
    assert len(prov["prompt_sha256"]) == 64
    assert prov["config_sha256"] == "config-hash"

    rule_partition = compute_partition_metrics(
        pipeline=Pipeline.RULE,
        mode="offline",
        claims=claims,
        citations=citations,
        judgments=[rule_judgment(supported=True)],
    )
    rule_prov = rule_partition.provenance
    assert rule_prov["adapter"] == "rule:offline"
    assert rule_prov["model_id"] is None


def test_partition_to_dict_is_json_safe() -> None:
    claims = [make_claim("c1")]
    citations = [make_citation("cite-1", "c1", "ev-1")]
    judgments = [rule_judgment(supported=True)]
    partition = compute_partition_metrics(
        pipeline=Pipeline.RULE,
        mode="offline",
        claims=claims,
        citations=citations,
        judgments=judgments,
    )
    payload = partition.to_dict()
    assert isinstance(payload["fingerprint"], str)
    assert payload["partition_id"] == "rule/offline"
    # round-trips through canonical JSON without loss or reordering surprises
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload
