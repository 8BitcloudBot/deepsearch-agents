"""P4-3 unit tests for the semantic support interface (offline deterministic).

Covers: mock decision (supported / unsupported / conflict / unknown), the
opt-in skip gate for the real adapter, timeout and malformed real output never
being support, redaction of reasons/limitations, deterministic fingerprints,
strict mock/real separation, and Phase 4 settings parsing.
"""

import re

import pytest

from app.citations.fixtures import SEED_CLAIMS, SEED_EVIDENCE
from app.citations.semantic import (
    DEFAULT_PROMPT_ID,
    MOCK_ADAPTER,
    SMOKE_ENV_VAR,
    SemanticMode,
    SemanticState,
    SemanticSupportChecker,
    canonical_sha256,
    render_prompt,
    summarize_semantic,
)
from app.settings import Phase4Settings

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _claim(claim_id: str) -> dict:
    return next(c for c in SEED_CLAIMS if c["claim_id"] == claim_id)


def _evidence(evidence_id: str) -> dict:
    return next(e for e in SEED_EVIDENCE if e["evidence_id"] == evidence_id)


# ---------------------------------------------------------------------------
# Mock decision (deterministic offline adapter)
# ---------------------------------------------------------------------------


def test_mock_supported_decision():
    j = SemanticSupportChecker().check(
        _claim("claim-001"), _evidence("evidence-001"), {}
    )
    assert j.state is SemanticState.SUPPORTED
    assert j.supported is True
    assert j.mode is SemanticMode.MOCK
    assert j.model_id == MOCK_ADAPTER


def test_mock_unsupported_decision():
    claim = {"claim_id": "c-x", "statement": "Bananas are yellow curved fruits."}
    evidence = {"evidence_id": "e-x", "quote": "The sky is blue on clear days."}
    j = SemanticSupportChecker().check(claim, evidence, {})
    assert j.state is SemanticState.UNSUPPORTED
    assert j.supported is False


def test_mock_conflict_decision():
    claim = {"claim_id": "c-y", "statement": "The service runs entirely online."}
    evidence = {
        "evidence_id": "e-y",
        "quote": "The service runs entirely offline without any network access.",
    }
    j = SemanticSupportChecker().check(claim, evidence, {})
    assert j.state is SemanticState.CONFLICT
    assert j.supported is False
    assert "without" in "\n".join(j.reasons)


def test_mock_unknown_on_malformed_input():
    for claim, evidence in (
        (42, "nope"),
        ({"claim_id": "c", "statement": ""}, {"evidence_id": "e", "quote": "x"}),
        ({"claim_id": "c", "statement": "x"}, {"evidence_id": "e", "quote": " "}),
        ({"claim_id": "c", "statement": "x"}, None),
    ):
        j = SemanticSupportChecker().check(claim, evidence, {})
        assert j.state is SemanticState.UNKNOWN
        assert j.supported is False


# ---------------------------------------------------------------------------
# Determinism + fingerprints
# ---------------------------------------------------------------------------


def test_mock_deterministic_byte_identical():
    checker = SemanticSupportChecker()
    a = checker.check(_claim("claim-002"), _evidence("evidence-002"), {})
    b = checker.check(_claim("claim-002"), _evidence("evidence-002"), {})
    assert a == b
    assert a.fingerprint == b.fingerprint
    assert a.prompt_sha256 == b.prompt_sha256
    assert a.config_sha256 == b.config_sha256


def test_prompt_and_config_fingerprints():
    claim, evidence = _claim("claim-001"), _evidence("evidence-001")
    j = SemanticSupportChecker().check(claim, evidence, {})
    assert j.prompt_id == DEFAULT_PROMPT_ID
    assert HEX64.match(j.prompt_sha256)
    assert HEX64.match(j.config_sha256)
    assert HEX64.match(j.fingerprint)
    assert j.prompt_sha256 == canonical_sha256(render_prompt(claim, evidence))

    other = SemanticSupportChecker(prompt_id="p4-semantic-support-v2").check(
        claim, evidence, {}
    )
    assert other.config_sha256 != j.config_sha256
    assert other.prompt_sha256 == j.prompt_sha256


# ---------------------------------------------------------------------------
# Opt-in real mode: skip without flag, timeout/malformed never support
# ---------------------------------------------------------------------------


def test_real_skipped_without_flag_no_credentials_no_network(monkeypatch):
    monkeypatch.delenv(SMOKE_ENV_VAR, raising=False)

    def _boom(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("real transport must not run without the opt-in flag")

    j = SemanticSupportChecker(
        adapter="real:openai:gpt-4.1-mini", transport=_boom
    ).check(_claim("claim-001"), _evidence("evidence-001"), {})
    assert j.state is SemanticState.SKIPPED
    assert j.supported is False
    assert j.mode is SemanticMode.REAL
    assert "opt-in" in "\n".join(j.reasons)
    assert "no credentials" in "\n".join(j.reasons)


def test_real_timeout_never_supported(monkeypatch):
    monkeypatch.setenv(SMOKE_ENV_VAR, "1")

    def _timeout(*args, **kwargs):
        raise TimeoutError("model call timed out")

    checker = SemanticSupportChecker(
        adapter="real:openai:gpt-4.1-mini",
        settings=Phase4Settings(real_semantic_smoke=True),
        transport=_timeout,
    )
    j = checker.check(_claim("claim-001"), _evidence("evidence-001"), {})
    assert j.state is SemanticState.UNKNOWN
    assert j.supported is False
    assert "timed out" in "\n".join(j.reasons)


def test_real_malformed_output_never_supported(monkeypatch):
    monkeypatch.setenv(SMOKE_ENV_VAR, "1")
    for bad in (
        "not json at all",
        {"state": "maybe"},
        {"state": "supported", "reasons": "not-a-list"},
    ):
        checker = SemanticSupportChecker(
            adapter="real:openai:gpt-4.1-mini",
            settings=Phase4Settings(real_semantic_smoke=True),
            transport=lambda *a, **k: bad,
        )
        j = checker.check(_claim("claim-001"), _evidence("evidence-001"), {})
        assert j.state is SemanticState.UNKNOWN
        assert j.supported is False


def test_real_supported_with_stub_and_context_timeout(monkeypatch):
    monkeypatch.setenv(SMOKE_ENV_VAR, "1")
    seen = {}

    def _stub(request, *, base_url, api_key, timeout_seconds):
        seen["timeout"] = timeout_seconds
        return {
            "state": "supported",
            "reasons": ["quote entails the claim"],
            "limitations": [],
        }

    checker = SemanticSupportChecker(
        adapter="real:openai:gpt-4.1-mini",
        settings=Phase4Settings(real_semantic_smoke=True),
        transport=_stub,
    )
    j = checker.check(
        _claim("claim-001"), _evidence("evidence-001"), {"timeout_seconds": 2.5}
    )
    assert seen["timeout"] == 2.5
    assert j.state is SemanticState.SUPPORTED
    assert j.supported is True
    assert j.mode is SemanticMode.REAL


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------


def test_mock_reason_redaction():
    secret = "api_key=hunter2"  # pragma: allowlist secret
    claim = {
        "claim_id": "c",
        "statement": f"DeepAgents supports single-agent patterns with {secret}.",
    }
    evidence = {
        "evidence_id": "e",
        "quote": f"DeepAgents supports single-agent patterns with {secret}.",
    }
    j = SemanticSupportChecker().check(claim, evidence, {})
    assert j.state is SemanticState.SUPPORTED
    blob = "\n".join(j.reasons)
    assert "hunter2" not in blob
    assert "<redacted>" in blob


def test_real_reason_and_limitation_redaction(monkeypatch):
    monkeypatch.setenv(SMOKE_ENV_VAR, "1")
    secret = "api_key=hunter2"  # pragma: allowlist secret
    path = "/Users/bob/private/notes.txt"
    token = "sk-ABCDEFGHIJKLMNOP"

    def _stub(*args, **kwargs):
        return {
            "state": "unknown",
            "reasons": [f"cannot verify {path} {secret} {token}"],
            "limitations": [f"model saw {token}"],
        }

    checker = SemanticSupportChecker(
        adapter="real:openai:gpt-4.1-mini",
        settings=Phase4Settings(real_semantic_smoke=True),
        transport=_stub,
    )
    j = checker.check(_claim("claim-001"), _evidence("evidence-001"), {})
    blob = "\n".join(j.reasons + j.limitations)
    assert "hunter2" not in blob
    assert "/Users/bob" not in blob
    assert "sk-ABCDEFGHIJKLMNOP" not in blob
    assert any(marker in blob for marker in ("<path>", "<secret>", "<redacted>"))


# ---------------------------------------------------------------------------
# Mock/real never aggregate; unknown/skipped never support
# ---------------------------------------------------------------------------


def test_mock_and_real_never_aggregate(monkeypatch):
    monkeypatch.delenv(SMOKE_ENV_VAR, raising=False)
    mock_j = SemanticSupportChecker().check(
        _claim("claim-001"), _evidence("evidence-001"), {}
    )
    real_j = SemanticSupportChecker(adapter="real:openai:gpt-4.1-mini").check(
        _claim("claim-002"), _evidence("evidence-002"), {}
    )
    assert mock_j.mode is SemanticMode.MOCK
    assert real_j.mode is SemanticMode.REAL
    with pytest.raises(ValueError, match="aggregate"):
        summarize_semantic((mock_j, real_j))


def test_summarize_never_counts_unknown_or_skipped_as_support(monkeypatch):
    monkeypatch.delenv(SMOKE_ENV_VAR, raising=False)
    supported = SemanticSupportChecker().check(
        _claim("claim-001"), _evidence("evidence-001"), {}
    )
    unknown = SemanticSupportChecker().check(42, "nope", {})
    skipped = SemanticSupportChecker(adapter="real:openai:gpt-4.1-mini").check(
        _claim("claim-002"), _evidence("evidence-002"), {}
    )
    mock_summary = summarize_semantic((supported, unknown))
    assert mock_summary["mode"] is SemanticMode.MOCK
    assert mock_summary["supported"] == 1
    assert mock_summary["unknown_or_skipped"] == 1
    assert mock_summary["states"]["unknown"] == 1

    real_summary = summarize_semantic((skipped,))
    assert real_summary["mode"] is SemanticMode.REAL
    assert real_summary["supported"] == 0
    assert real_summary["unknown_or_skipped"] == 1


# ---------------------------------------------------------------------------
# Phase 4 settings
# ---------------------------------------------------------------------------


def test_phase4_settings_from_env():
    assert Phase4Settings.from_env({}).real_semantic_smoke is False
    assert (
        Phase4Settings.from_env({"PHASE4_REAL_SEMANTIC_SMOKE": "0"}).real_semantic_smoke
        is False
    )
    assert (
        Phase4Settings.from_env({"PHASE4_REAL_SEMANTIC_SMOKE": "1"}).real_semantic_smoke
        is True
    )

    s = Phase4Settings.from_env(
        {
            "PHASE4_REAL_SEMANTIC_MODEL": "openai:gpt-4o-mini",
            "PHASE4_REAL_SEMANTIC_TIMEOUT_SECONDS": "45.5",
        }
    )
    assert s.real_semantic_model == "openai:gpt-4o-mini"
    assert s.real_semantic_timeout_seconds == 45.5

    fallback = Phase4Settings.from_env({"MODEL_NAME": "openai:gpt-4.1"})
    assert fallback.real_semantic_model == "openai:gpt-4.1"
    assert fallback.real_semantic_base_url is None
    assert fallback.real_semantic_api_key is None
