"""Canonical Phase 4 seed-10 citation fixture (offline, immutable).

Ten cases, each with a first-class Claim, an EvidenceItem quoting an exact
bounded span of one of the three frozen Phase 3 sources, and a CitationRecord
linking them. The fixture text is fully deterministic (sorted keys, compact
separators, UTF-8, one record per line, trailing newline), so its sha256
fingerprint is stable. The fingerprint is recorded in ``manifest.json`` and
re-checked by :func:`app.citations.contracts.load_fixture` on every load.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.citations.contracts import PHASE3_SOURCES, load_fixture

FIXTURE_NAME = "seed-10"
FIXTURE_PATH = Path("data/phase4/citations/seed-10.jsonl")
MANIFEST_PATH = Path("data/phase4/citations/manifest.json")

WEB_HASH = PHASE3_SOURCES["web-agent-frameworks-v1"]["content_sha256"]
CATALOG_HASH = PHASE3_SOURCES["catalog-frameworks-v1"]["content_sha256"]
KNOWLEDGE_HASH = PHASE3_SOURCES["knowledge-evaluation-notes-v1"]["content_sha256"]

SEED_CLAIMS: tuple[dict[str, Any], ...] = (
    {
        "type": "claim",
        "claim_id": "claim-001",
        "statement": (
            "DeepAgents supports single-agent and orchestrator-workers "
            "execution patterns."
        ),
    },
    {
        "type": "claim",
        "claim_id": "claim-002",
        "statement": (
            "Deterministic local execution enables offline evaluation without "
            "network access."
        ),
    },
    {
        "type": "claim",
        "claim_id": "claim-003",
        "statement": (
            "Tool events are emitted per source family so evaluation can "
            "attribute content to Web, Catalog or Knowledge."
        ),
    },
    {
        "type": "claim",
        "claim_id": "claim-004",
        "statement": (
            "Multi-agent conversation is flexible but harder to keep deterministic."
        ),
    },
    {
        "type": "claim",
        "claim_id": "claim-005",
        "statement": (
            "The DeepAgents catalog entry lists single-agent / "
            "orchestrator-workers orchestration with offline evaluation support."
        ),
    },
    {
        "type": "claim",
        "claim_id": "claim-006",
        "statement": (
            "LangGraph is catalogued with graph orchestration and offline "
            "evaluation support."
        ),
    },
    {
        "type": "claim",
        "claim_id": "claim-007",
        "statement": (
            "Framework choice is an empirical question decided by measured "
            "baselines, not defaults."
        ),
    },
    {
        "type": "claim",
        "claim_id": "claim-008",
        "statement": (
            "Every evaluation number is bound to corpus, model identity, prompt "
            "identity, configuration fingerprint, strategy and Git commit."
        ),
    },
    {
        "type": "claim",
        "claim_id": "claim-009",
        "statement": "Case files are immutable once a dataset version is frozen.",
    },
    {
        "type": "claim",
        "claim_id": "claim-010",
        "statement": (
            "Reports may merge offline and real Provider evidence without "
            "separating them."
        ),
    },
)

SEED_EVIDENCE: tuple[dict[str, Any], ...] = (
    {
        "type": "evidence",
        "evidence_id": "evidence-001",
        "source_id": "web-agent-frameworks-v1",
        "source_kind": "web_snapshot",
        "content_sha256": WEB_HASH,
        "locator": {"kind": "anchor", "value": "agent-framework-landscape"},
        "quote": (
            "DeepAgents supports single-agent and orchestrator-workers "
            "execution patterns."
        ),
    },
    {
        "type": "evidence",
        "evidence_id": "evidence-002",
        "source_id": "web-agent-frameworks-v1",
        "source_kind": "web_snapshot",
        "content_sha256": WEB_HASH,
        "locator": {"kind": "section", "value": "Offline evaluation"},
        "quote": (
            "Deterministic local execution enables offline evaluation without "
            "network access."
        ),
    },
    {
        "type": "evidence",
        "evidence_id": "evidence-003",
        "source_id": "web-agent-frameworks-v1",
        "source_kind": "web_snapshot",
        "content_sha256": WEB_HASH,
        "locator": {"kind": "paragraph", "value": "2"},
        "quote": (
            "Tool events are emitted per source family so evaluation can "
            "attribute content to Web, Catalog or Knowledge."
        ),
    },
    {
        "type": "evidence",
        "evidence_id": "evidence-004",
        "source_id": "web-agent-frameworks-v1",
        "source_kind": "web_snapshot",
        "content_sha256": WEB_HASH,
        "locator": {"kind": "url", "value": "https://docs.deepagents.ai/"},
        "quote": (
            "Multi-agent conversation: agents exchange messages toward a "
            "consensus; flexible but harder to keep deterministic."
        ),
    },
    {
        "type": "evidence",
        "evidence_id": "evidence-005",
        "source_id": "catalog-frameworks-v1",
        "source_kind": "catalog",
        "content_sha256": CATALOG_HASH,
        "locator": {"kind": "row", "value": "DeepAgents"},
        "quote": "| DeepAgents | single-agent / orchestrator-workers | yes |",
    },
    {
        "type": "evidence",
        "evidence_id": "evidence-006",
        "source_id": "catalog-frameworks-v1",
        "source_kind": "catalog",
        "content_sha256": CATALOG_HASH,
        "locator": {"kind": "row", "value": "LangGraph"},
        "quote": "| LangGraph | graph orchestration | yes |",
    },
    {
        "type": "evidence",
        "evidence_id": "evidence-007",
        "source_id": "catalog-frameworks-v1",
        "source_kind": "catalog",
        "content_sha256": CATALOG_HASH,
        "locator": {"kind": "paragraph", "value": "1"},
        "quote": (
            "Framework choice is an empirical question: run the same seed cases "
            "under each strategy and compare measured baselines."
        ),
    },
    {
        "type": "evidence",
        "evidence_id": "evidence-008",
        "source_id": "knowledge-evaluation-notes-v1",
        "source_kind": "knowledge",
        "content_sha256": KNOWLEDGE_HASH,
        "locator": {"kind": "line", "value": "7"},
        "quote": (
            "Every evaluation number is bound to dataset/version hash, corpus "
            "ID, model identity, prompt identity, configuration fingerprint, "
            "strategy and Git commit."
        ),
    },
    {
        "type": "evidence",
        "evidence_id": "evidence-009",
        "source_id": "knowledge-evaluation-notes-v1",
        "source_kind": "knowledge",
        "content_sha256": KNOWLEDGE_HASH,
        "locator": {"kind": "line", "value": "22"},
        "quote": (
            "Case files are immutable once a dataset version is frozen; any "
            "edit changes the file hash recorded in the dataset manifest."
        ),
    },
    {
        "type": "evidence",
        "evidence_id": "evidence-010",
        "source_id": "knowledge-evaluation-notes-v1",
        "source_kind": "knowledge",
        "content_sha256": KNOWLEDGE_HASH,
        "locator": {"kind": "section", "value": "Metrics"},
        "quote": (
            "Reports separate offline evidence from real Provider evidence and "
            "record skipped reasons explicitly."
        ),
    },
)

SEED_CITATIONS: tuple[dict[str, Any], ...] = (
    {
        "type": "citation",
        "id": "cite-001",
        "claim_id": "claim-001",
        "evidence_id": "evidence-001",
        "support": "supports",
        "conflict": "none",
        "version": "1.0.0",
    },
    {
        "type": "citation",
        "id": "cite-002",
        "claim_id": "claim-002",
        "evidence_id": "evidence-002",
        "support": "supports",
        "conflict": "none",
        "version": "1.0.0",
    },
    {
        "type": "citation",
        "id": "cite-003",
        "claim_id": "claim-003",
        "evidence_id": "evidence-003",
        "support": "supports",
        "conflict": "none",
        "version": "1.0.0",
    },
    {
        "type": "citation",
        "id": "cite-004",
        "claim_id": "claim-004",
        "evidence_id": "evidence-004",
        "support": "supports",
        "conflict": "none",
        "version": "1.0.0",
    },
    {
        "type": "citation",
        "id": "cite-005",
        "claim_id": "claim-005",
        "evidence_id": "evidence-005",
        "support": "supports",
        "conflict": "none",
        "version": "1.1.0",
    },
    {
        "type": "citation",
        "id": "cite-006",
        "claim_id": "claim-006",
        "evidence_id": "evidence-006",
        "support": "supports",
        "conflict": "none",
        "version": "1.1.0",
    },
    {
        "type": "citation",
        "id": "cite-007",
        "claim_id": "claim-007",
        "evidence_id": "evidence-007",
        "support": "neutral",
        "conflict": "unresolved",
        "version": "1.2.0",
    },
    {
        "type": "citation",
        "id": "cite-008",
        "claim_id": "claim-008",
        "evidence_id": "evidence-008",
        "support": "supports",
        "conflict": "none",
        "version": "2.0.0",
    },
    {
        "type": "citation",
        "id": "cite-009",
        "claim_id": "claim-009",
        "evidence_id": "evidence-009",
        "support": "supports",
        "conflict": "resolved",
        "version": "1.0.0",
    },
    {
        "type": "citation",
        "id": "cite-010",
        "claim_id": "claim-010",
        "evidence_id": "evidence-010",
        "support": "contradicts",
        "conflict": "unresolved",
        "version": "1.0.0-rc.1",
    },
)

SEED_10: tuple[dict[str, Any], ...] = tuple(
    record
    for case in zip(SEED_CLAIMS, SEED_EVIDENCE, SEED_CITATIONS)
    for record in case
)


def render_seed_10() -> str:
    """Deterministic JSONL text for the canonical seed-10 fixture."""
    lines = [
        json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for record in SEED_10
    ]
    return "\n".join(lines) + "\n"


def fingerprint(text: str) -> str:
    """sha256 hex digest of the UTF-8 encoding of ``text``."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def seed_10_fingerprint() -> str:
    """Stable fingerprint of the canonical seed-10 fixture text."""
    return fingerprint(render_seed_10())


def write_seed_10(path: Path = FIXTURE_PATH) -> Path:
    """Write the canonical fixture to ``path`` (deterministic bytes)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_seed_10(), encoding="utf-8")
    return path


def load_seed_10() -> dict[str, Any]:
    """Load the canonical fixture through the strict manifest contract."""
    return load_fixture(MANIFEST_PATH, FIXTURE_PATH)
