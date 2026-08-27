"""Phase 4 P4-1: first-class Claim / EvidenceItem / CitationRecord contracts
and the immutable seed-10 fixture bound to the frozen Phase 3 sources.

Contracts fail closed for IDs, link references, enumerated states, unknown
fields, unsafe paths, wrong hashes, cross-source locators, and evidence quotes
that are not exact bounded spans of their frozen source content.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.citations import contracts as C  # noqa: E402, N812
from app.citations import fixtures as F  # noqa: E402, N812

MANIFEST_PATH = ROOT / "data/phase4/citations/manifest.json"
SEED_PATH = ROOT / "data/phase4/citations/seed-10.jsonl"
PHASE3_ROOT = ROOT / "data/phase3/sources"

WEB_HASH = C.PHASE3_SOURCES["web-agent-frameworks-v1"]["content_sha256"]
CATALOG_HASH = C.PHASE3_SOURCES["catalog-frameworks-v1"]["content_sha256"]
KNOWLEDGE_HASH = C.PHASE3_SOURCES["knowledge-evaluation-notes-v1"]["content_sha256"]


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def source_text(source_id: str) -> str:
    """The locatable text of a frozen Phase 3 source (JSON ``content`` or raw)."""
    meta = C.PHASE3_SOURCES[source_id]
    raw = (PHASE3_ROOT / meta["path"]).read_text(encoding="utf-8")
    if raw.lstrip().startswith("{"):
        return json.loads(raw)["content"]
    return raw


def base_claim(**overrides) -> dict:
    claim = {
        "type": "claim",
        "claim_id": "claim-001",
        "statement": (
            "DeepAgents supports single-agent and orchestrator-workers "
            "execution patterns."
        ),
    }
    claim.update(overrides)
    return claim


def base_evidence(**overrides) -> dict:
    evidence = {
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
    }
    evidence.update(overrides)
    return evidence


def base_citation(**overrides) -> dict:
    citation = {
        "type": "citation",
        "id": "cite-001",
        "claim_id": "claim-001",
        "evidence_id": "evidence-001",
        "support": "supports",
        "conflict": "none",
        "version": "1.0.0",
    }
    citation.update(overrides)
    return citation


def render(records: list[dict]) -> str:
    return "".join(
        json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        for r in records
    )


def write_pair(
    tmp_path: Path, manifest: dict, records: list[dict]
) -> tuple[Path, Path]:
    """Write a manifest + fixture pair whose fingerprint matches the records."""
    text = render(records)
    fixture = tmp_path / "fixture.jsonl"
    fixture.write_text(text, encoding="utf-8")
    m = json.loads(json.dumps(manifest))
    m["fixture"] = dict(m["fixture"])
    m["fixture"]["count"] = len(records)
    m["fixture"]["fingerprint"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(m, sort_keys=True), encoding="utf-8")
    return manifest_file, fixture


def load_records(tmp_path: Path, records: list[dict]) -> dict:
    manifest_file, fixture = write_pair(tmp_path, load_manifest(), records)
    return C.load_fixture(manifest_file, fixture)


def evidence_for(source_id: str, source_kind: str, locator: dict) -> dict:
    """A base evidence bound to the given frozen source (correct hash)."""
    return base_evidence(
        source_id=source_id,
        source_kind=source_kind,
        content_sha256=C.PHASE3_SOURCES[source_id]["content_sha256"],
        locator=locator,
    )


def trio(**overrides) -> list[dict]:
    return [base_claim(), base_evidence(), base_citation(**overrides)]


class TestClaimContract:
    """First-class Claim: claim_id + statement fail closed."""

    @pytest.mark.parametrize("field", ["claim_id", "statement"])
    def test_missing_required_field_rejected(self, field: str) -> None:
        claim = {k: v for k, v in base_claim().items() if k != field}
        with pytest.raises(C.CitationError) as exc:
            C.validate_claim(claim)
        assert field in str(exc.value)

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(C.CitationError) as exc:
            C.validate_claim(base_claim(extra="x"))
        assert "extra" in str(exc.value)

    def test_non_object_rejected(self) -> None:
        with pytest.raises(C.CitationError):
            C.validate_claim("not-an-object")

    def test_wrong_record_type_rejected(self) -> None:
        with pytest.raises(C.CitationError):
            C.validate_claim(base_claim(type="citation"))

    @pytest.mark.parametrize("value", ["claim-", "CL-001", "claim_001", ""])
    def test_malformed_claim_id_rejected(self, value: str) -> None:
        with pytest.raises(C.CitationError) as exc:
            C.validate_claim(base_claim(claim_id=value))
        assert "claim_id" in str(exc.value)

    @pytest.mark.parametrize("statement", ["", "   ", 42, "x" * 1025])
    def test_invalid_statement_rejected(self, statement: object) -> None:
        with pytest.raises(C.CitationError):
            C.validate_claim(base_claim(statement=statement))

    def test_control_char_statement_rejected(self) -> None:
        with pytest.raises(C.CitationError):
            C.validate_claim(base_claim(statement="line\nbreak"))

    def test_valid_claim_roundtrips(self) -> None:
        claim = C.validate_claim(base_claim())
        assert json.loads(json.dumps(claim)) == claim


class TestEvidenceContract:
    """First-class EvidenceItem: real source identity, hash, locator, quote."""

    @pytest.mark.parametrize(
        "field",
        [
            "evidence_id",
            "source_id",
            "source_kind",
            "content_sha256",
            "locator",
            "quote",
        ],
    )
    def test_missing_required_field_rejected(self, field: str) -> None:
        evidence = {k: v for k, v in base_evidence().items() if k != field}
        with pytest.raises(C.CitationError) as exc:
            C.validate_evidence(evidence)
        assert field in str(exc.value)

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(C.CitationError) as exc:
            C.validate_evidence(base_evidence(extra="x"))
        assert "extra" in str(exc.value)

    def test_non_object_rejected(self) -> None:
        with pytest.raises(C.CitationError):
            C.validate_evidence("not-an-object")

    def test_wrong_record_type_rejected(self) -> None:
        with pytest.raises(C.CitationError):
            C.validate_evidence(base_evidence(type="claim"))

    def test_malformed_evidence_id_rejected(self) -> None:
        with pytest.raises(C.CitationError):
            C.validate_evidence(base_evidence(evidence_id="claim-001"))

    @pytest.mark.parametrize(
        "source_id", ["source-ghost-001", "source-doc-001", "web", ""]
    )
    def test_unknown_source_id_rejected(self, source_id: str) -> None:
        with pytest.raises(C.CitationError) as exc:
            C.validate_evidence(base_evidence(source_id=source_id))
        assert "source_id" in str(exc.value)

    def test_source_kind_mismatch_rejected(self) -> None:
        with pytest.raises(C.CitationError) as exc:
            C.validate_evidence(base_evidence(source_kind="knowledge"))
        assert "source_kind" in str(exc.value)

    def test_content_sha256_mismatch_rejected(self) -> None:
        with pytest.raises(C.CitationError) as exc:
            C.validate_evidence(base_evidence(content_sha256="0" * 64))
        assert "content_sha256" in str(exc.value)

    def test_malformed_content_sha256_rejected(self) -> None:
        with pytest.raises(C.CitationError):
            C.validate_evidence(base_evidence(content_sha256="zzz"))

    @pytest.mark.parametrize(
        ("source_id", "source_kind", "locator"),
        [
            (
                "web-agent-frameworks-v1",
                "web_snapshot",
                {"kind": "url", "value": "https://docs.deepagents.ai/"},
            ),
            (
                "web-agent-frameworks-v1",
                "web_snapshot",
                {"kind": "anchor", "value": "offline-evaluation"},
            ),
            (
                "web-agent-frameworks-v1",
                "web_snapshot",
                {"kind": "section", "value": "Orchestration patterns"},
            ),
            (
                "catalog-frameworks-v1",
                "catalog",
                {"kind": "row", "value": "DeepAgents"},
            ),
            ("catalog-frameworks-v1", "catalog", {"kind": "paragraph", "value": "1"}),
            (
                "knowledge-evaluation-notes-v1",
                "knowledge",
                {"kind": "line", "value": "7"},
            ),
            (
                "knowledge-evaluation-notes-v1",
                "knowledge",
                {"kind": "section", "value": "Metrics"},
            ),
        ],
    )
    def test_allowed_locator_accepted(
        self, source_id: str, source_kind: str, locator: dict
    ) -> None:
        evidence = C.validate_evidence(evidence_for(source_id, source_kind, locator))
        assert evidence["locator"] == locator

    @pytest.mark.parametrize(
        ("source_id", "source_kind", "locator"),
        [
            ("catalog-frameworks-v1", "catalog", {"kind": "line", "value": "7"}),
            (
                "catalog-frameworks-v1",
                "catalog",
                {"kind": "url", "value": "https://x.example"},
            ),
            (
                "knowledge-evaluation-notes-v1",
                "knowledge",
                {"kind": "row", "value": "DeepAgents"},
            ),
            (
                "knowledge-evaluation-notes-v1",
                "knowledge",
                {"kind": "anchor", "value": "metrics"},
            ),
            (
                "web-agent-frameworks-v1",
                "web_snapshot",
                {"kind": "row", "value": "DeepAgents"},
            ),
            ("web-agent-frameworks-v1", "web_snapshot", {"kind": "line", "value": "7"}),
        ],
    )
    def test_cross_source_locator_rejected(
        self, source_id: str, source_kind: str, locator: dict
    ) -> None:
        with pytest.raises(C.CitationError) as exc:
            C.validate_evidence(evidence_for(source_id, source_kind, locator))
        assert "locator" in str(exc.value)

    def test_locator_unknown_field_rejected(self) -> None:
        locator = {"kind": "anchor", "value": "x", "extra": 1}
        with pytest.raises(C.CitationError):
            C.validate_evidence(base_evidence(locator=locator))

    def test_locator_missing_value_rejected(self) -> None:
        with pytest.raises(C.CitationError):
            C.validate_evidence(base_evidence(locator={"kind": "anchor"}))

    def test_empty_locator_value_rejected(self) -> None:
        with pytest.raises(C.CitationError):
            C.validate_evidence(base_evidence(locator={"kind": "anchor", "value": ""}))

    @pytest.mark.parametrize("quote", ["", "   ", 42, "x" * 513])
    def test_invalid_quote_rejected(self, quote: object) -> None:
        with pytest.raises(C.CitationError):
            C.validate_evidence(base_evidence(quote=quote))

    def test_padded_quote_rejected(self) -> None:
        with pytest.raises(C.CitationError):
            C.validate_evidence(base_evidence(quote=" span with padding "))

    def test_control_char_quote_rejected(self) -> None:
        with pytest.raises(C.CitationError):
            C.validate_evidence(base_evidence(quote="line\nbreak"))

    def test_valid_evidence_roundtrips(self) -> None:
        evidence = C.validate_evidence(base_evidence())
        assert json.loads(json.dumps(evidence)) == evidence


class TestCitationRecordContract:
    """First-class CitationRecord: id, link references, states, version."""

    @pytest.mark.parametrize(
        "field", ["id", "claim_id", "evidence_id", "support", "conflict", "version"]
    )
    def test_missing_required_field_rejected(self, field: str) -> None:
        citation = {k: v for k, v in base_citation().items() if k != field}
        with pytest.raises(C.CitationError) as exc:
            C.validate_citation(citation)
        assert field in str(exc.value)

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(C.CitationError) as exc:
            C.validate_citation(base_citation(extra="x"))
        assert "extra" in str(exc.value)

    def test_non_object_rejected(self) -> None:
        with pytest.raises(C.CitationError):
            C.validate_citation("not-an-object")

    def test_wrong_record_type_rejected(self) -> None:
        with pytest.raises(C.CitationError):
            C.validate_citation(base_citation(type="evidence"))

    @pytest.mark.parametrize("value", ["CITE-001", "cite_001", "cite-", ""])
    def test_malformed_citation_id_rejected(self, value: str) -> None:
        with pytest.raises(C.CitationError) as exc:
            C.validate_citation(base_citation(id=value))
        assert "id" in str(exc.value)

    def test_evidence_reference_in_claim_namespace_rejected(self) -> None:
        with pytest.raises(C.CitationError):
            C.validate_citation(base_citation(evidence_id="claim-001"))

    def test_claim_reference_in_evidence_namespace_rejected(self) -> None:
        with pytest.raises(C.CitationError):
            C.validate_citation(base_citation(claim_id="evidence-001"))

    @pytest.mark.parametrize("support", ["partial", "SUPPORTS", "unknown"])
    def test_invalid_support_rejected(self, support: str) -> None:
        with pytest.raises(C.CitationError) as exc:
            C.validate_citation(base_citation(support=support))
        assert "support" in str(exc.value)

    @pytest.mark.parametrize("conflict", ["pending", "CONFLICT", "unknown"])
    def test_invalid_conflict_rejected(self, conflict: str) -> None:
        with pytest.raises(C.CitationError) as exc:
            C.validate_citation(base_citation(conflict=conflict))
        assert "conflict" in str(exc.value)

    @pytest.mark.parametrize("version", ["1.0", "v1.0.0", "1.0.0.1", "abc", "1..0"])
    def test_invalid_version_rejected(self, version: str) -> None:
        with pytest.raises(C.CitationError) as exc:
            C.validate_citation(base_citation(version=version))
        assert "version" in str(exc.value)

    def test_prerelease_version_accepted(self) -> None:
        citation = C.validate_citation(base_citation(version="1.0.0-rc.1"))
        assert citation["version"] == "1.0.0-rc.1"

    def test_valid_citation_roundtrips(self) -> None:
        citation = C.validate_citation(base_citation())
        assert json.loads(json.dumps(citation)) == citation


class TestManifestContract:
    """Manifest must bind exactly the frozen Phase 3 source records."""

    def test_real_manifest_valid(self) -> None:
        C.validate_manifest(load_manifest())

    def test_wrong_schema_version_rejected(self) -> None:
        manifest = load_manifest()
        manifest["schema_version"] = "0.9.0"
        with pytest.raises(C.ManifestError):
            C.validate_manifest(manifest)

    def test_unknown_manifest_field_rejected(self) -> None:
        manifest = load_manifest()
        manifest["extra"] = 1
        with pytest.raises(C.ManifestError) as exc:
            C.validate_manifest(manifest)
        assert "extra" in str(exc.value)

    def test_fixture_unknown_field_rejected(self) -> None:
        manifest = load_manifest()
        manifest["fixture"]["extra"] = 1
        with pytest.raises(C.ManifestError):
            C.validate_manifest(manifest)

    def test_source_entry_unknown_field_rejected(self) -> None:
        manifest = load_manifest()
        manifest["sources"]["web-agent-frameworks-v1"]["extra"] = 1
        with pytest.raises(C.ManifestError):
            C.validate_manifest(manifest)

    def test_unknown_source_added_rejected(self) -> None:
        manifest = load_manifest()
        manifest["sources"]["source-ghost-001"] = {
            "kind": "web_snapshot",
            "path": "web/ghost.json",
            "hash": "0" * 64,
        }
        with pytest.raises(C.ManifestError) as exc:
            C.validate_manifest(manifest)
        assert "source-ghost-001" in str(exc.value)

    def test_missing_source_rejected(self) -> None:
        manifest = load_manifest()
        del manifest["sources"]["catalog-frameworks-v1"]
        with pytest.raises(C.ManifestError):
            C.validate_manifest(manifest)

    def test_source_kind_mismatch_rejected(self) -> None:
        manifest = load_manifest()
        manifest["sources"]["web-agent-frameworks-v1"]["kind"] = "knowledge"
        with pytest.raises(C.ManifestError):
            C.validate_manifest(manifest)

    def test_source_hash_mismatch_rejected(self) -> None:
        manifest = load_manifest()
        manifest["sources"]["web-agent-frameworks-v1"]["hash"] = "0" * 64
        with pytest.raises(C.ManifestError):
            C.validate_manifest(manifest)

    def test_source_path_mismatch_rejected(self) -> None:
        manifest = load_manifest()
        manifest["sources"]["web-agent-frameworks-v1"]["path"] = "web/other.json"
        with pytest.raises(C.ManifestError):
            C.validate_manifest(manifest)

    @pytest.mark.parametrize(
        "path", ["/etc/passwd", "../secret.txt", "a\\b.json", "a/../b.json"]
    )
    def test_unsafe_source_paths_rejected(self, path: str) -> None:
        manifest = load_manifest()
        manifest["sources"]["web-agent-frameworks-v1"]["path"] = path
        with pytest.raises(C.ManifestError):
            C.validate_manifest(manifest)

    def test_malformed_source_hash_rejected(self) -> None:
        manifest = load_manifest()
        manifest["sources"]["web-agent-frameworks-v1"]["hash"] = "zzz"
        with pytest.raises(C.ManifestError) as exc:
            C.validate_manifest(manifest)
        assert "hash" in str(exc.value)

    def test_malformed_fingerprint_rejected(self) -> None:
        manifest = load_manifest()
        manifest["fixture"]["fingerprint"] = "abc"
        with pytest.raises(C.ManifestError):
            C.validate_manifest(manifest)

    def test_unknown_fingerprint_algorithm_rejected(self) -> None:
        manifest = load_manifest()
        manifest["fixture"]["fingerprint_algorithm"] = "md5"
        with pytest.raises(C.ManifestError):
            C.validate_manifest(manifest)

    def test_non_positive_count_rejected(self) -> None:
        manifest = load_manifest()
        manifest["fixture"]["count"] = 0
        with pytest.raises(C.ManifestError):
            C.validate_manifest(manifest)


class TestFixtureIntegrity:
    """Seed-10 is immutable, offline, and bound to real Phase 3 sources."""

    def test_seed_10_has_ten_of_each_record(self) -> None:
        result = C.load_fixture(MANIFEST_PATH, SEED_PATH)
        assert len(result["claims"]) == 10
        assert len(result["evidence"]) == 10
        assert len(result["citations"]) == 10

    def test_fingerprint_matches_file_bytes(self) -> None:
        actual = hashlib.sha256(SEED_PATH.read_bytes()).hexdigest()
        assert actual == load_manifest()["fixture"]["fingerprint"]

    def test_fingerprint_matches_canonical_render(self) -> None:
        assert F.seed_10_fingerprint() == load_manifest()["fixture"]["fingerprint"]

    def test_fixture_bytes_are_canonical(self) -> None:
        assert SEED_PATH.read_text(encoding="utf-8") == F.render_seed_10()

    def test_no_duplicate_ids(self) -> None:
        result = C.load_fixture(MANIFEST_PATH, SEED_PATH)
        id_keys = {"claims": "claim_id", "evidence": "evidence_id", "citations": "id"}
        for key, id_key in id_keys.items():
            ids = [r[id_key] for r in result[key]]
            assert len(ids) == len(set(ids)), key

    def test_citation_claim_references_resolve(self) -> None:
        result = C.load_fixture(MANIFEST_PATH, SEED_PATH)
        claims = {c["claim_id"] for c in result["claims"]}
        for citation in result["citations"]:
            assert citation["claim_id"] in claims

    def test_citation_evidence_references_resolve(self) -> None:
        result = C.load_fixture(MANIFEST_PATH, SEED_PATH)
        evidence = {e["evidence_id"] for e in result["evidence"]}
        for citation in result["citations"]:
            assert citation["evidence_id"] in evidence

    def test_every_source_is_a_real_phase3_source(self) -> None:
        result = C.load_fixture(MANIFEST_PATH, SEED_PATH)
        used = {e["source_id"] for e in result["evidence"]}
        assert used == set(C.PHASE3_SOURCES)

    def test_evidence_source_linkage_matches_manifest(self) -> None:
        result = C.load_fixture(MANIFEST_PATH, SEED_PATH)
        for evidence in result["evidence"]:
            entry = result["manifest"]["sources"][evidence["source_id"]]
            assert evidence["source_kind"] == entry["kind"]
            assert evidence["content_sha256"] == entry["hash"]

    def test_every_evidence_quote_is_an_exact_span(self) -> None:
        result = C.load_fixture(MANIFEST_PATH, SEED_PATH)
        for evidence in result["evidence"]:
            text = source_text(evidence["source_id"])
            assert evidence["quote"] in text
            assert len(evidence["quote"]) < len(text)

    def test_claims_roundtrip_through_json(self) -> None:
        for claim in C.load_fixture(MANIFEST_PATH, SEED_PATH)["claims"]:
            assert C.validate_claim(json.loads(json.dumps(claim))) == claim

    def test_evidence_roundtrip_through_json(self) -> None:
        for evidence in C.load_fixture(MANIFEST_PATH, SEED_PATH)["evidence"]:
            assert C.validate_evidence(json.loads(json.dumps(evidence))) == evidence

    def test_citations_roundtrip_through_json(self) -> None:
        for citation in C.load_fixture(MANIFEST_PATH, SEED_PATH)["citations"]:
            assert C.validate_citation(json.loads(json.dumps(citation))) == citation


class TestLoadFailClosed:
    """Malformed fixtures and linkage must fail closed at load time."""

    def test_duplicate_citation_id_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(C.CitationError) as exc:
            load_records(tmp_path, trio() + [base_citation()])
        assert "duplicate" in str(exc.value)

    def test_duplicate_claim_id_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(C.CitationError) as exc:
            load_records(tmp_path, [base_claim(), base_claim()])
        assert "duplicate" in str(exc.value)

    def test_duplicate_evidence_id_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(C.CitationError) as exc:
            load_records(tmp_path, [base_evidence(), base_evidence()])
        assert "duplicate" in str(exc.value)

    def test_citation_referencing_unknown_claim_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(C.CitationError) as exc:
            load_records(tmp_path, trio(claim_id="claim-999"))
        assert "claim-999" in str(exc.value)

    def test_citation_referencing_unknown_evidence_rejected(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(C.CitationError) as exc:
            load_records(tmp_path, trio(evidence_id="evidence-999"))
        assert "evidence-999" in str(exc.value)

    def test_evidence_with_unknown_source_rejected(self, tmp_path: Path) -> None:
        records = [
            base_claim(),
            base_evidence(source_id="source-ghost-001"),
            base_citation(),
        ]
        with pytest.raises(C.CitationError) as exc:
            load_records(tmp_path, records)
        assert "source-ghost-001" in str(exc.value)

    def test_evidence_source_kind_mismatch_rejected(self, tmp_path: Path) -> None:
        records = [
            base_claim(),
            base_evidence(source_kind="knowledge"),
            base_citation(),
        ]
        with pytest.raises(C.CitationError):
            load_records(tmp_path, records)

    def test_evidence_hash_mismatch_rejected(self, tmp_path: Path) -> None:
        records = [
            base_claim(),
            base_evidence(content_sha256="0" * 64),
            base_citation(),
        ]
        with pytest.raises(C.CitationError):
            load_records(tmp_path, records)

    def test_cross_source_locator_rejected_at_load(self, tmp_path: Path) -> None:
        records = [
            base_claim(),
            base_evidence(
                source_id="knowledge-evaluation-notes-v1",
                source_kind="knowledge",
                content_sha256=KNOWLEDGE_HASH,
                locator={"kind": "row", "value": "DeepAgents"},
                quote="Case files are immutable once a dataset version is frozen; "
                "any edit changes the file hash recorded in the dataset manifest.",
            ),
            base_citation(),
        ]
        with pytest.raises(C.CitationError):
            load_records(tmp_path, records)

    def test_quote_not_a_span_rejected(self, tmp_path: Path) -> None:
        records = [
            base_claim(),
            base_evidence(quote="this exact text is absent from the web snapshot"),
            base_citation(),
        ]
        with pytest.raises(C.CitationError) as exc:
            load_records(tmp_path, records)
        assert "quote" in str(exc.value)

    def test_quote_covering_whole_source_rejected(self, tmp_path: Path) -> None:
        records = [
            base_claim(),
            base_evidence(quote=source_text("web-agent-frameworks-v1")),
            base_citation(),
        ]
        with pytest.raises(C.CitationError) as exc:
            load_records(tmp_path, records)
        assert "quote" in str(exc.value)

    def test_fingerprint_mismatch_rejected(self, tmp_path: Path) -> None:
        manifest_file, fixture = write_pair(tmp_path, load_manifest(), trio())
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        manifest["fixture"]["fingerprint"] = "0" * 64
        manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
        with pytest.raises(C.ManifestError) as exc:
            C.load_fixture(manifest_file, fixture)
        assert "fingerprint" in str(exc.value)

    def test_count_mismatch_rejected(self, tmp_path: Path) -> None:
        manifest_file, fixture = write_pair(tmp_path, load_manifest(), trio())
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        manifest["fixture"]["count"] = 2
        manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
        with pytest.raises(C.ManifestError):
            C.load_fixture(manifest_file, fixture)

    def test_manifest_source_hash_vs_phase3_rejected(self, tmp_path: Path) -> None:
        manifest_file, fixture = write_pair(tmp_path, load_manifest(), trio())
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        manifest["sources"]["web-agent-frameworks-v1"]["hash"] = "0" * 64
        manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
        with pytest.raises(C.ManifestError):
            C.load_fixture(manifest_file, fixture)
