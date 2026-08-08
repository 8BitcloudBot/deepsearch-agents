"""Deterministic offline lexical/structural rule support checks (P4-2).

``RuleSupportChecker.check(claim, evidence)`` returns a structured
:class:`SupportJudgment` computed purely from the P4-1 Claim / EvidenceItem
dicts. It is pure and deterministic: no I/O, no network, no Provider, no
randomness, and it never raises on malformed input.

Rules (stable ids, evaluated in this order):

* ``r0_structure``    -- claim/evidence are JSON objects with non-empty
  ``statement`` and ``quote`` strings.
* ``r5_source_known`` -- ``source_id`` must be a frozen Phase 3 source and
  ``source_kind`` must agree with the frozen record.
* ``r4_source_fresh`` -- ``content_sha256`` must equal the frozen Phase 3
  source record hash; a mismatch means the evidence is stale.
* ``r3_locator_valid`` -- the locator must be a JSON object with a non-empty
  ``kind``/``value``; the kind must be allowed for the source kind.
* ``r1_exact_quote``  -- the claim statement is an exact span of the quote
  (whitespace-normalized containment).
* ``r2_token_overlap`` -- the fraction of claim tokens (casefolded ASCII
  alphanumeric runs) present in the quote must meet the per-source-kind
  threshold from :data:`SOURCE_POLICY`.
* ``r6_no_conflict``  -- a would-be-supported match is downgraded to
  ``contradicted`` when the quote introduces a negation term absent from the
  claim.

Fail-closed: any structural failure, unknown source, stale hash, or malformed
locator yields verdict ``invalid``; a detected conflict yields ``contradicted``;
insufficient overlap yields ``unsupported``. Unknown, stale, and conflicting
matches are never upgraded to ``supported``.

All human-readable reasons are redacted (absolute paths, URL credentials, and
secret-like values are masked), and every judgment carries a stable sha256
``fingerprint`` of its canonical payload, so identical inputs produce
byte-identical judgments.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.citations.contracts import (
    LOCATOR_KINDS,
    MAX_LOCATOR_VALUE_LENGTH,
    PHASE3_SOURCES,
    SourceKind,
)

# Stable rule identifiers. These are part of the P4-2 contract: they never
# change between runs or versions, so judgments stay comparable over time.
RULE_STRUCTURE = "r0_structure"
RULE_EXACT_QUOTE = "r1_exact_quote"
RULE_TOKEN_OVERLAP = "r2_token_overlap"
RULE_LOCATOR_VALID = "r3_locator_valid"
RULE_SOURCE_FRESH = "r4_source_fresh"
RULE_SOURCE_KNOWN = "r5_source_known"
RULE_NO_CONFLICT = "r6_no_conflict"

ALL_RULE_IDS: tuple[str, ...] = (
    RULE_STRUCTURE,
    RULE_EXACT_QUOTE,
    RULE_TOKEN_OVERLAP,
    RULE_LOCATOR_VALID,
    RULE_SOURCE_FRESH,
    RULE_SOURCE_KNOWN,
    RULE_NO_CONFLICT,
)

MAX_FRAGMENT_LENGTH = 160


class Verdict(StrEnum):
    """Stable, deterministic support verdicts (fail-closed by construction)."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    INVALID = "invalid"


@dataclass(frozen=True)
class SourcePolicy:
    """Per-source-kind lexical policy; thresholds are fixed and deterministic."""

    min_overlap: float


# Source-level policy: prose-ish snapshots/notes tolerate lower overlap than
# terse catalog rows, which must be near-verbatim to support a claim.
SOURCE_POLICY: dict[SourceKind, SourcePolicy] = {
    SourceKind.WEB_SNAPSHOT: SourcePolicy(min_overlap=0.60),
    SourceKind.CATALOG: SourcePolicy(min_overlap=0.80),
    SourceKind.KNOWLEDGE: SourcePolicy(min_overlap=0.65),
}

# Casefolded tokens that signal contradiction when they appear in the quote
# but NOT in the claim. Conservative by design: the rule only fires on a match
# that would otherwise be supported, so it never upgrades a conflict and never
# penalizes a negation the claim itself already contains (e.g. "offline
# evaluation without network access").
NEGATION_TOKENS: frozenset[str] = frozenset(
    {
        "not",
        "no",
        "nor",
        "never",
        "without",
        "cannot",
        "cant",
        "dont",
        "doesnt",
        "didnt",
        "wont",
        "isnt",
        "arent",
        "lacks",
        "absent",
        "denies",
        "rejects",
        "refuses",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_WS_RE = re.compile(r"\s+")

_PATH_REDACTED = "<path>"
_SECRET_REDACTED = "<secret>"
_VALUE_REDACTED = "<redacted>"

# Ordered redaction passes; each is deterministic and idempotent on output.
_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    # URL credentials: scheme://user:pass@host -> scheme://<redacted>@host
    (
        re.compile(r"(?i)([a-z][a-z0-9+.-]*://)[^/@\s]+@"),
        rf"\g<1>{_VALUE_REDACTED}@",
    ),
    # Windows absolute paths: C:\Users\... -> <path>
    (re.compile(r"[A-Za-z]:\\[A-Za-z0-9._~\\ -]+"), _PATH_REDACTED),
    # POSIX absolute paths (not inside URLs, which use "//" or ":" before "/")
    (
        re.compile(r"(?<![\w:/])/[A-Za-z0-9._~-]+(?:/[A-Za-z0-9._~-]+)+"),
        _PATH_REDACTED,
    ),
    # key=value secrets: password=hunter2 -> password=<redacted>
    (
        re.compile(
            r"(?i)\b(password|passwd|secret|token|api[_-]?key|authorization)(\s*[:=]\s*)\S+"
        ),
        rf"\g<1>\g<2>{_VALUE_REDACTED}",
    ),
    # sk- prefixed API tokens -> <secret>
    (re.compile(r"(?i)\bsk-[A-Za-z0-9_-]{8,}\b"), _SECRET_REDACTED),
    # Long opaque runs (hashes/keys/base64) -> <secret>
    (re.compile(r"\b[A-Za-z0-9+/=_-]{24,}\b"), _SECRET_REDACTED),
)


def tokenize(text: str) -> tuple[str, ...]:
    """Casefolded ASCII alphanumeric runs of ``text`` (deterministic)."""
    return tuple(_TOKEN_RE.findall(text.casefold()))


def _normalized_ws(text: str) -> str:
    return _WS_RE.sub(" ", text.strip())


def redact(text: str) -> str:
    """Mask paths, URL credentials, and secret-like values in ``text``."""
    out = text
    for pattern, replacement in _REDACTIONS:
        out = pattern.sub(replacement, out)
    return out


def _fragment(text: str) -> str:
    """Bounded, redacted excerpt of raw text for use inside reasons."""
    truncated = text[:MAX_FRAGMENT_LENGTH]
    if len(text) > MAX_FRAGMENT_LENGTH:
        truncated += "..."
    return redact(truncated)


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SupportJudgment:
    """Structured, deterministic outcome of one claim/evidence check."""

    supported: bool
    verdict: Verdict
    score: float
    matched_tokens: tuple[str, ...]
    rules: tuple[str, ...]
    reasons: tuple[str, ...]
    fingerprint: str


class RuleSupportChecker:
    """Pure, stateless, deterministic rule support checker (P4-2).

    ``check`` never raises: structurally unusable input yields an ``invalid``
    judgment, keeping the checker fail-closed by construction.
    """

    def check(self, claim: Any, evidence: Any) -> SupportJudgment:
        """Judge whether ``evidence`` supports ``claim`` (lexical/structural)."""
        if not isinstance(claim, Mapping) or not isinstance(evidence, Mapping):
            return self._make(
                Verdict.INVALID,
                0.0,
                (),
                [RULE_STRUCTURE],
                ["claim and evidence must be JSON objects (rule r0)"],
                "",
                "",
            )
        claim_id = claim.get("claim_id")
        evidence_id = evidence.get("evidence_id")

        # r0: structural shape.
        rules: list[str] = [RULE_STRUCTURE]
        statement = claim.get("statement")
        quote = evidence.get("quote")
        if not isinstance(statement, str) or not statement.strip():
            return self._invalid(
                rules,
                "claim statement must be a non-empty string (rule r0)",
                claim_id,
                evidence_id,
            )
        if not isinstance(quote, str) or not quote.strip():
            return self._invalid(
                rules,
                "evidence quote must be a non-empty string (rule r0)",
                claim_id,
                evidence_id,
            )

        # r5: the source must be a known, correctly-typed Phase 3 source.
        rules.append(RULE_SOURCE_KNOWN)
        source_id = evidence.get("source_id")
        frozen = PHASE3_SOURCES.get(source_id) if isinstance(source_id, str) else None
        if frozen is None:
            return self._invalid(
                rules,
                f"source_id {source_id!r} is not a frozen Phase 3 source (rule r5)",
                claim_id,
                evidence_id,
            )
        if evidence.get("source_kind") != frozen["kind"]:
            return self._invalid(
                rules,
                f"source_id {source_id!r} declares source_kind "
                f"{evidence.get('source_kind')!r} but the frozen record is "
                f"{frozen['kind']!r} (rule r5)",
                claim_id,
                evidence_id,
            )
        source_kind = SourceKind(frozen["kind"])

        # r4: stale evidence (content hash drift) never supports.
        rules.append(RULE_SOURCE_FRESH)
        if evidence.get("content_sha256") != frozen["content_sha256"]:
            return self._invalid(
                rules,
                "evidence content hash is stale: does not match the frozen "
                "Phase 3 source record (rule r4)",
                claim_id,
                evidence_id,
            )

        # r3: locator shape and kind-vs-source-kind compatibility.
        rules.append(RULE_LOCATOR_VALID)
        locator = evidence.get("locator")
        if not isinstance(locator, Mapping):
            return self._invalid(
                rules,
                "locator must be a JSON object with kind and value (rule r3)",
                claim_id,
                evidence_id,
            )
        locator_kind = locator.get("kind")
        locator_value = locator.get("value")
        if not isinstance(locator_kind, str) or not locator_kind:
            return self._invalid(
                rules,
                "locator.kind must be a non-empty string (rule r3)",
                claim_id,
                evidence_id,
            )
        if not isinstance(locator_value, str) or not locator_value:
            return self._invalid(
                rules,
                "locator.value must be a non-empty string (rule r3)",
                claim_id,
                evidence_id,
            )
        if len(locator_value) > MAX_LOCATOR_VALUE_LENGTH:
            return self._invalid(
                rules,
                f"locator.value must be at most {MAX_LOCATOR_VALUE_LENGTH} "
                "characters (rule r3)",
                claim_id,
                evidence_id,
            )
        if any(ord(ch) < 0x20 for ch in locator_value):
            return self._invalid(
                rules,
                "locator.value must not contain control characters (rule r3)",
                claim_id,
                evidence_id,
            )
        if locator_kind not in LOCATOR_KINDS[source_kind]:
            return self._invalid(
                rules,
                f"locator kind {locator_kind!r} is not valid for source kind "
                f"{source_kind.value!r} (rule r3)",
                claim_id,
                evidence_id,
            )

        # r1/r2: exact containment or per-source token overlap.
        claim_tokens = tokenize(statement)
        quote_tokens = set(tokenize(quote))
        matched = tuple(sorted(set(claim_tokens) & quote_tokens))
        score = len(matched) / len(claim_tokens) if claim_tokens else 0.0
        policy = SOURCE_POLICY[source_kind]

        rules.append(RULE_EXACT_QUOTE)
        exact = _normalized_ws(statement) in _normalized_ws(quote)
        rules.append(RULE_TOKEN_OVERLAP)
        meets_threshold = score >= policy.min_overlap

        if exact or meets_threshold:
            # Candidate support: guard against lexical conflict (r6).
            rules.append(RULE_NO_CONFLICT)
            negations = sorted((quote_tokens & NEGATION_TOKENS) - set(claim_tokens))
            if negations:
                return self._make(
                    Verdict.CONTRADICTED,
                    score,
                    matched,
                    rules,
                    [
                        "evidence quote introduces negation term(s) absent "
                        f"from the claim: {', '.join(negations)} (rule r6)"
                    ],
                    claim_id,
                    evidence_id,
                )
            if exact:
                reasons = [
                    "claim statement is an exact span of the evidence quote "
                    f"(rule r1): {_fragment(statement)}"
                ]
                return self._make(
                    Verdict.SUPPORTED,
                    score,
                    matched,
                    rules,
                    reasons,
                    claim_id,
                    evidence_id,
                )
            reasons = [
                f"token overlap {score:.2f} meets the {policy.min_overlap:.2f} "
                f"{source_kind.value} threshold (rule r2)"
            ]
            return self._make(
                Verdict.SUPPORTED, score, matched, rules, reasons, claim_id, evidence_id
            )

        reasons = [
            f"token overlap {score:.2f} is below the {policy.min_overlap:.2f} "
            f"{source_kind.value} threshold (rule r2)"
        ]
        return self._make(
            Verdict.UNSUPPORTED, score, matched, rules, reasons, claim_id, evidence_id
        )

    def _invalid(
        self,
        rules: list[str],
        reason: str,
        claim_id: Any = "",
        evidence_id: Any = "",
    ) -> SupportJudgment:
        return self._make(
            Verdict.INVALID, 0.0, (), rules, [reason], claim_id, evidence_id
        )

    @staticmethod
    def _make(
        verdict: Verdict,
        score: float,
        matched_tokens: tuple[str, ...],
        rules: list[str],
        reasons: list[str],
        claim_id: Any,
        evidence_id: Any,
    ) -> SupportJudgment:
        redacted = tuple(redact(reason) for reason in reasons)
        fingerprint = _fingerprint(
            {
                "verdict": verdict.value,
                "score": f"{score:.6f}",
                "rules": list(rules),
                "matched_tokens": list(matched_tokens),
                "reasons": list(redacted),
                "claim_id": str(claim_id),
                "evidence_id": str(evidence_id),
            }
        )
        return SupportJudgment(
            supported=verdict is Verdict.SUPPORTED,
            verdict=verdict,
            score=score,
            matched_tokens=matched_tokens,
            rules=tuple(rules),
            reasons=redacted,
            fingerprint=fingerprint,
        )


__all__ = [
    "ALL_RULE_IDS",
    "MAX_FRAGMENT_LENGTH",
    "NEGATION_TOKENS",
    "RULE_EXACT_QUOTE",
    "RULE_LOCATOR_VALID",
    "RULE_NO_CONFLICT",
    "RULE_SOURCE_FRESH",
    "RULE_SOURCE_KNOWN",
    "RULE_STRUCTURE",
    "RULE_TOKEN_OVERLAP",
    "SOURCE_POLICY",
    "RuleSupportChecker",
    "SourcePolicy",
    "SupportJudgment",
    "Verdict",
    "redact",
    "tokenize",
]
