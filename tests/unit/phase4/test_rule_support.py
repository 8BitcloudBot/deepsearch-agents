"""Phase 4-2 (P4-2): deterministic offline lexical/structural rule support checks.

TDD contract for ``RuleSupportChecker.check(claim, evidence)`` over the P4-1
Claim / EvidenceItem dicts. The checker is pure and deterministic: it never
touches the network, the Provider, metrics, the API, or the filesystem, and it
never upgrades an unknown, stale, or conflicting match to ``supported``
(fail-closed).
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from app.citations.contracts import PHASE3_SOURCES, SourceKind
from app.citations.fixtures import SEED_CITATIONS, SEED_CLAIMS, SEED_EVIDENCE
from app.citations.rules import (
    RULE_EXACT_QUOTE,
    RULE_LOCATOR_VALID,
    RULE_NO_CONFLICT,
    RULE_SOURCE_FRESH,
    RULE_SOURCE_KNOWN,
    RULE_TOKEN_OVERLAP,
    SOURCE_POLICY,
    RuleSupportChecker,
    SupportJudgment,
    Verdict,
)

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def make_claim(statement: str, claim_id: str = "claim-t1") -> dict[str, str]:
    """A valid P4-1 Claim dict."""
    return {"type": "claim", "claim_id": claim_id, "statement": statement}


def make_evidence(
    quote: str,
    *,
    source_id: str = "web-agent-frameworks-v1",
    locator: Any | None = None,
    content_sha256: str | None = None,
    evidence_id: str = "evidence-t1",
) -> dict[str, Any]:
    """A P4-1 EvidenceItem dict; unknown sources fall back to a stale hash."""
    source = PHASE3_SOURCES.get(source_id)
    return {
        "type": "evidence",
        "evidence_id": evidence_id,
        "source_id": source_id,
        "source_kind": source["kind"] if source else "web_snapshot",
        "content_sha256": (
            content_sha256
            if content_sha256 is not None
            else (source["content_sha256"] if source else "0" * 64)
        ),
        "locator": locator
        if locator is not None
        else {"kind": "section", "value": "1"},
        "quote": quote,
    }


@pytest.fixture(scope="module")
def checker() -> RuleSupportChecker:
    return RuleSupportChecker()


def test_exact_quote_containment_supports(checker: RuleSupportChecker) -> None:
    statement = (
        "DeepAgents supports single-agent and orchestrator-workers execution patterns."
    )
    judgment = checker.check(make_claim(statement), make_evidence(statement))
    assert isinstance(judgment, SupportJudgment)
    assert judgment.supported is True
    assert judgment.verdict is Verdict.SUPPORTED
    assert RULE_EXACT_QUOTE in judgment.rules
    assert judgment.score == pytest.approx(1.0)
    assert judgment.matched_tokens
    assert _SHA256_HEX.fullmatch(judgment.fingerprint)

    # A shorter claim exactly contained in a longer quote still counts.
    statement = "Case files are immutable once a dataset version is frozen."
    quote = (
        statement + " any edit changes the file hash recorded in the dataset manifest."
    )
    nested = checker.check(make_claim(statement, "claim-t1b"), make_evidence(quote))
    assert nested.supported is True
    assert nested.verdict is Verdict.SUPPORTED
    assert RULE_EXACT_QUOTE in nested.rules


def test_token_mismatch_is_unsupported(checker: RuleSupportChecker) -> None:
    judgment = checker.check(
        make_claim("Quantum entangled toasters drive the meta-framework."),
        make_evidence("DeepAgents supports single-agent execution patterns."),
    )
    assert judgment.supported is False
    assert judgment.verdict is Verdict.UNSUPPORTED
    assert RULE_TOKEN_OVERLAP in judgment.rules
    assert judgment.score == pytest.approx(0.0)
    assert "overlap" in " ".join(judgment.reasons).lower()


def test_malformed_locator_fails_closed(checker: RuleSupportChecker) -> None:
    statement = "DeepAgents supports single-agent execution patterns."

    # Locator kind not valid for this source kind (line is knowledge-only).
    bad_kind = checker.check(
        make_claim(statement),
        make_evidence(statement, locator={"kind": "line", "value": "7"}),
    )
    assert bad_kind.supported is False
    assert bad_kind.verdict is Verdict.INVALID
    assert RULE_LOCATOR_VALID in bad_kind.rules
    assert "locator" in " ".join(bad_kind.reasons).lower()

    # Locator is not a JSON object at all.
    not_mapping = checker.check(
        make_claim(statement), make_evidence(statement, locator="bad")
    )
    assert not_mapping.supported is False
    assert not_mapping.verdict is Verdict.INVALID
    assert RULE_LOCATOR_VALID in not_mapping.rules


def test_stale_source_fails_closed(checker: RuleSupportChecker) -> None:
    statement = "DeepAgents supports single-agent execution patterns."

    # content_sha256 does not match the frozen Phase 3 source record.
    stale = checker.check(
        make_claim(statement),
        make_evidence(statement, content_sha256="0" * 64),
    )
    assert stale.supported is False
    assert stale.verdict is Verdict.INVALID
    assert RULE_SOURCE_FRESH in stale.rules
    assert "stale" in " ".join(stale.reasons).lower()

    # Unknown source_id is never supported either.
    unknown = checker.check(
        make_claim(statement), make_evidence(statement, source_id="unknown-source-v1")
    )
    assert unknown.supported is False
    assert unknown.verdict is Verdict.INVALID
    assert RULE_SOURCE_KNOWN in unknown.rules


def test_conflicting_evidence_never_supported(checker: RuleSupportChecker) -> None:
    # High overlap, but the quote introduces a negation absent from the claim.
    judgment = checker.check(
        make_claim("DeepAgents supports single-agent execution."),
        make_evidence("DeepAgents does not support single-agent execution."),
    )
    assert judgment.supported is False
    assert judgment.verdict is Verdict.CONTRADICTED
    assert RULE_NO_CONFLICT in judgment.rules

    # Regression: a negation present in the claim itself ("without network
    # access") must not flip an exact, genuinely supporting match.
    statement = (
        "Deterministic local execution enables offline evaluation without "
        "network access."
    )
    regression = checker.check(make_claim(statement), make_evidence(statement))
    assert regression.supported is True
    assert regression.verdict is Verdict.SUPPORTED


def test_secret_and_path_redaction(checker: RuleSupportChecker) -> None:
    secret_path = "/Users/alice/.ssh/id_rsa"
    secret_token = "sk-live-abcdef123456"  # pragma: allowlist secret
    secret_value = "z9y8x7w6v5u4"  # pragma: allowlist secret
    statement = f"Rotate {secret_path} with {secret_token} and token={secret_value}."
    judgment = checker.check(make_claim(statement), make_evidence(statement))
    assert judgment.verdict is Verdict.SUPPORTED  # exact containment holds
    for reason in judgment.reasons:
        assert secret_path not in reason
        assert secret_token not in reason
        assert secret_value not in reason
    joined = " | ".join(judgment.reasons)
    assert "<path>" in joined
    assert "<secret>" in joined
    assert "<redacted>" in joined

    # Redaction also applies on the failure path (malformed locator whose
    # value carries a credential).
    bad = checker.check(
        make_claim("DeepAgents supports single-agent execution patterns."),
        make_evidence(
            "DeepAgents supports single-agent execution patterns.",
            locator={"kind": "line", "value": "creds password=hunter2"},
        ),
    )
    assert bad.verdict is Verdict.INVALID
    for reason in bad.reasons:
        assert "hunter2" not in reason


def test_deterministic_result_and_fingerprint(checker: RuleSupportChecker) -> None:
    statement = (
        "LangGraph is catalogued with graph orchestration and offline "
        "evaluation support."
    )
    quote = "| LangGraph | graph orchestration | yes |"
    kwargs: dict[str, Any] = {
        "source_id": "catalog-frameworks-v1",
        "locator": {"kind": "row", "value": "LangGraph"},
        "evidence_id": "evidence-det",
    }
    first = checker.check(
        make_claim(statement, "claim-det"), make_evidence(quote, **kwargs)
    )
    second = checker.check(
        make_claim(statement, "claim-det"), make_evidence(quote, **kwargs)
    )
    assert first == second
    assert first.fingerprint == second.fingerprint
    assert _SHA256_HEX.fullmatch(first.fingerprint)

    # A second, stateless checker instance reproduces the exact judgment.
    other_checker = RuleSupportChecker()
    assert (
        other_checker.check(
            make_claim(statement, "claim-det"), make_evidence(quote, **kwargs)
        )
        == first
    )

    # Different input (claim id) changes the fingerprint.
    different = checker.check(
        make_claim(statement, "claim-det-other"), make_evidence(quote, **kwargs)
    )
    assert different.fingerprint != first.fingerprint


def test_source_level_policy_thresholds(checker: RuleSupportChecker) -> None:
    # 7 of 10 claim tokens are present in the quote: overlap is 0.70.
    statement = "alpha bravo charlie delta echo foxtrot golf hotel india juliet"
    quote = "alpha bravo charlie delta echo foxtrot golf alpha bravo charlie"

    assert SOURCE_POLICY[SourceKind.WEB_SNAPSHOT].min_overlap == pytest.approx(0.60)
    assert SOURCE_POLICY[SourceKind.CATALOG].min_overlap == pytest.approx(0.80)
    assert SOURCE_POLICY[SourceKind.KNOWLEDGE].min_overlap == pytest.approx(0.65)

    web = checker.check(
        make_claim(statement, "claim-policy"),
        make_evidence(quote, evidence_id="evidence-policy"),
    )
    assert web.verdict is Verdict.SUPPORTED
    assert RULE_TOKEN_OVERLAP in web.rules
    assert web.score == pytest.approx(0.70)

    catalog = checker.check(
        make_claim(statement, "claim-policy"),
        make_evidence(
            quote,
            source_id="catalog-frameworks-v1",
            locator={"kind": "row", "value": "DeepAgents"},
            evidence_id="evidence-policy",
        ),
    )
    assert catalog.verdict is Verdict.UNSUPPORTED
    assert catalog.supported is False
    assert catalog.score == pytest.approx(0.70)

    knowledge = checker.check(
        make_claim(statement, "claim-policy"),
        make_evidence(
            quote,
            source_id="knowledge-evaluation-notes-v1",
            locator={"kind": "line", "value": "7"},
            evidence_id="evidence-policy",
        ),
    )
    assert knowledge.verdict is Verdict.SUPPORTED
    assert knowledge.score == pytest.approx(0.70)


def test_malformed_input_fails_closed(checker: RuleSupportChecker) -> None:
    statement = "DeepAgents supports single-agent execution patterns."

    not_a_mapping = checker.check(None, make_evidence(statement))
    assert not_a_mapping.supported is False
    assert not_a_mapping.verdict is Verdict.INVALID

    missing_quote = checker.check(make_claim(statement), {"type": "evidence"})
    assert missing_quote.supported is False
    assert missing_quote.verdict is Verdict.INVALID


def test_never_upgrades_fixture_conflicts(checker: RuleSupportChecker) -> None:
    """P4-1 citations labeled contradicts / unresolved must stay unsupported."""
    # A citation whose conflict is "resolved" in favor of support is not a
    # live conflict (cite-009 supports/resolved), so only contradicts /
    # unresolved / neutral citations must stay unsupported.
    for citation, claim, evidence in zip(
        SEED_CITATIONS, SEED_CLAIMS, SEED_EVIDENCE, strict=True
    ):
        if citation["support"] != "supports" or citation["conflict"] == "unresolved":
            judgment = checker.check(claim, evidence)
            assert judgment.supported is False, (
                f"citation {citation['id']!r} ({citation['support']} / "
                f"{citation['conflict']}) was upgraded to supported"
            )
