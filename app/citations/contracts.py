"""Strict, serializable contracts for Phase 4 citation data (P4-1).

First-class, JSON-serializable records:

* :class:`Claim`            -- ``claim_id`` + ``statement``
* :class:`EvidenceItem`     -- a quote extracted from one frozen Phase 3
  source, carrying that source's real identity (``source_id``, ``source_kind``,
  ``content_sha256``) and an allowed locator
* :class:`CitationRecord`   -- links one Claim to one EvidenceItem with a
  support and conflict state plus a semantic version

Everything fails closed: unknown fields, malformed ids, unknown enumerated
states, unsafe paths, malformed hashes, unknown sources, cross-source
locators, non-span quotes, unresolved link references, duplicate ids, and
fingerprint mismatches are rejected with :class:`CitationError` or
:class:`ManifestError`. Validated records and manifests are plain JSON-safe
dicts, so they round-trip through serialization unchanged.

The frozen Phase 3 source identities (``PHASE3_SOURCES``) are the only
allowed evidence sources; the Phase 4 manifest must bind exactly those
source records and their true content hashes.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "2.0.0"
FINGERPRINT_ALGORITHM = "sha256"

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_PATH_RE = re.compile(r"^[A-Za-z0-9_./-]+$")
_ABSOLUTE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")

_ID_PATTERNS = {
    "id": r"^cite-[A-Za-z0-9][A-Za-z0-9_-]*$",
    "claim_id": r"^claim-[A-Za-z0-9][A-Za-z0-9_-]*$",
    "evidence_id": r"^evidence-[A-Za-z0-9][A-Za-z0-9_-]*$",
    "source_id": r"^[a-z][a-z0-9-]{0,63}$",
}
_ID_RES = {name: re.compile(pattern) for name, pattern in _ID_PATTERNS.items()}

CLAIM_FIELDS = frozenset({"type", "claim_id", "statement"})
EVIDENCE_FIELDS = frozenset(
    {
        "type",
        "evidence_id",
        "source_id",
        "source_kind",
        "content_sha256",
        "locator",
        "quote",
    }
)
CITATION_FIELDS = frozenset(
    {"type", "id", "claim_id", "evidence_id", "support", "conflict", "version"}
)
LOCATOR_FIELDS = frozenset({"kind", "value"})
MANIFEST_FIELDS = frozenset({"schema_version", "fixture", "sources"})
FIXTURE_FIELDS = frozenset(
    {"name", "file", "count", "fingerprint_algorithm", "fingerprint"}
)
SOURCE_FIELDS = frozenset({"kind", "path", "hash"})

MAX_STATEMENT_LENGTH = 1024
MAX_QUOTE_LENGTH = 512
MAX_LOCATOR_VALUE_LENGTH = 512

# Frozen Phase 3 source identities. These are the ONLY allowed evidence
# sources; content hashes are the true sha256 of the frozen source files as
# recorded in data/phase3/sources/manifest.json.
PHASE3_SOURCES: dict[str, dict[str, str]] = {
    "web-agent-frameworks-v1": {
        "kind": "web_snapshot",
        "path": "web/agent-frameworks.json",
        "content_sha256": (
            "794bed8459aca36698d8fe6bb2b749c"  # pragma: allowlist secret
            "0ff003d0e36ff629cbae51536f314ddeb"  # pragma: allowlist secret
        ),
    },
    "catalog-frameworks-v1": {
        "kind": "catalog",
        "path": "catalog/frameworks.json",
        "content_sha256": (
            "aa8005363b8a0dd8e9e118797fca644a"  # pragma: allowlist secret
            "c7745edf7456864c7261557dfac7bbcb"  # pragma: allowlist secret
        ),
    },
    "knowledge-evaluation-notes-v1": {
        "kind": "knowledge",
        "path": "knowledge/evaluation-notes.md",
        "content_sha256": (
            "fea0ad2368c20d6c1e9e8f1e02759d13"  # pragma: allowlist secret
            "b0598d001448d70c991e60626690d6c6"  # pragma: allowlist secret
        ),
    },
}


class CitationError(ValueError):
    """A claim, evidence item, citation, or fixture violated the contract."""

    def __init__(self, message: str, *, path: str = "$") -> None:
        super().__init__(f"{path}: {message}")
        self.path = path


class ManifestError(ValueError):
    """A manifest or fixture violated the strict manifest contract."""

    def __init__(self, message: str, *, path: str = "$") -> None:
        super().__init__(f"{path}: {message}")
        self.path = path


class RecordType(StrEnum):
    CLAIM = "claim"
    EVIDENCE = "evidence"
    CITATION = "citation"


class SourceKind(StrEnum):
    WEB_SNAPSHOT = "web_snapshot"
    CATALOG = "catalog"
    KNOWLEDGE = "knowledge"


class SupportState(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"


class ConflictState(StrEnum):
    NONE = "none"
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"


LOCATOR_KINDS = {
    SourceKind.WEB_SNAPSHOT: frozenset({"url", "anchor", "section", "paragraph"}),
    SourceKind.CATALOG: frozenset({"row", "section", "paragraph"}),
    SourceKind.KNOWLEDGE: frozenset({"line", "section", "paragraph"}),
}


def _check_fields(
    raw: Any,
    required: frozenset[str],
    what: str,
    path: str,
    error_cls: type[ValueError] = CitationError,
) -> None:
    if not isinstance(raw, Mapping):
        raise error_cls(f"{what} must be a JSON object", path=path)
    unknown = sorted(set(raw) - set(required))
    if unknown:
        raise error_cls(f"{what} has unknown field(s): {', '.join(unknown)}", path=path)
    missing = sorted(set(required) - set(raw))
    if missing:
        raise error_cls(
            f"{what} is missing required field(s): {', '.join(missing)}", path=path
        )


def _enum(
    raw: Any,
    enum_cls: type[StrEnum],
    field: str,
    path: str,
    error_cls: type[ValueError] = CitationError,
) -> StrEnum:
    if not isinstance(raw, str):
        raise error_cls(f"{field} must be a string", path=f"{path}.{field}")
    try:
        return enum_cls(raw)
    except ValueError:
        allowed = ", ".join(sorted(member.value for member in enum_cls))
        raise error_cls(f"{field} must be one of: {allowed}", path=f"{path}.{field}")


def _id(
    raw: Any,
    field: str,
    path: str,
    error_cls: type[ValueError] = CitationError,
) -> str:
    if not isinstance(raw, str):
        raise error_cls(f"{field} must be a string", path=f"{path}.{field}")
    if not _ID_RES[field].fullmatch(raw):
        raise error_cls(
            f"{field} is malformed; expected pattern {_ID_PATTERNS[field]!r}",
            path=f"{path}.{field}",
        )
    return raw


def _version(
    raw: Any,
    field: str,
    path: str,
    error_cls: type[ValueError] = CitationError,
) -> str:
    if not isinstance(raw, str):
        raise error_cls(f"{field} must be a string", path=f"{path}.{field}")
    if not _SEMVER_RE.fullmatch(raw):
        raise error_cls(
            f"{field} must be a valid semantic version (e.g. 1.2.3 or 1.2.3-rc.1)",
            path=f"{path}.{field}",
        )
    return raw


def _safe_path(
    raw: Any,
    field: str,
    path: str,
    error_cls: type[ValueError] = ManifestError,
) -> str:
    if not isinstance(raw, str) or not raw:
        raise error_cls(f"{field} must be a non-empty string", path=f"{path}.{field}")
    if raw.startswith("/") or _ABSOLUTE_PATH_RE.match(raw):
        raise error_cls(
            f"{field} must be a relative path, got {raw!r}", path=f"{path}.{field}"
        )
    if "\\" in raw:
        raise error_cls(f"{field} must use forward slashes", path=f"{path}.{field}")
    if not _SAFE_PATH_RE.fullmatch(raw):
        raise error_cls(
            f"{field} contains disallowed characters", path=f"{path}.{field}"
        )
    if any(segment in ("", ".", "..") for segment in raw.split("/")):
        raise error_cls(
            f"{field} must not contain empty, '.' or '..' segments",
            path=f"{path}.{field}",
        )
    return raw


def _sha256_hash(
    raw: Any, field: str, path: str, error_cls: type[ValueError] = ManifestError
) -> str:
    if not isinstance(raw, str) or not _SHA256_RE.fullmatch(raw):
        raise error_cls(
            f"{field} must be a 64-character lowercase sha256 hex digest",
            path=f"{path}.{field}",
        )
    return raw


def _text(
    raw: Any,
    field: str,
    path: str,
    max_length: int,
    error_cls: type[ValueError] = CitationError,
) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise error_cls(f"{field} must be a non-empty string", path=f"{path}.{field}")
    if len(raw) > max_length:
        raise error_cls(
            f"{field} must be at most {max_length} characters",
            path=f"{path}.{field}",
        )
    if any(ord(ch) < 0x20 for ch in raw):
        raise error_cls(
            f"{field} must not contain control characters", path=f"{path}.{field}"
        )
    return raw


def _locator(raw: Any, source_kind: SourceKind, path: str) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        raise CitationError("locator must be a JSON object", path=f"{path}.locator")
    _check_fields(raw, LOCATOR_FIELDS, "locator", f"{path}.locator")
    kind, value = raw["kind"], raw["value"]
    if not isinstance(kind, str) or not kind:
        raise CitationError(
            "locator.kind must be a non-empty string", path=f"{path}.locator.kind"
        )
    if not isinstance(value, str) or not value:
        raise CitationError(
            "locator.value must be a non-empty string", path=f"{path}.locator.value"
        )
    if len(value) > MAX_LOCATOR_VALUE_LENGTH:
        raise CitationError(
            f"locator.value must be at most {MAX_LOCATOR_VALUE_LENGTH} characters",
            path=f"{path}.locator.value",
        )
    if any(ord(ch) < 0x20 for ch in value):
        raise CitationError(
            "locator.value must not contain control characters",
            path=f"{path}.locator.value",
        )
    allowed = LOCATOR_KINDS[source_kind]
    if kind not in allowed:
        raise CitationError(
            "locator kind {!r} is not valid for source kind {!r}; allowed: {}".format(
                kind, source_kind.value, ", ".join(sorted(allowed))
            ),
            path=f"{path}.locator.kind",
        )
    return {"kind": kind, "value": value}


def _record_type(raw: Any, expected: RecordType, path: str) -> RecordType:
    record_type = _enum(raw.get("type"), RecordType, "type", path)
    if record_type is not expected:
        raise CitationError(
            f"type must be {expected.value!r}, got {record_type.value!r}",
            path=f"{path}.type",
        )
    return record_type


def validate_claim(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a first-class Claim, returning a normalized JSON-safe dict.

    Raises :class:`CitationError` on any violation. Fail-closed checks:
    unknown/missing fields, record type, id pattern, and statement shape.
    """
    path = "$"
    _check_fields(raw, CLAIM_FIELDS, "claim", path)
    _record_type(raw, RecordType.CLAIM, path)
    return {
        "type": RecordType.CLAIM.value,
        "claim_id": _id(raw["claim_id"], "claim_id", path),
        "statement": _text(raw["statement"], "statement", path, MAX_STATEMENT_LENGTH),
    }


def validate_evidence(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a first-class EvidenceItem, returning a normalized dict.

    Raises :class:`CitationError` on any violation. Fail-closed checks:
    unknown/missing fields, record type, id pattern, unknown source, source
    kind and content_sha256 agreement with the frozen Phase 3 source record,
    locator-vs-source-kind compatibility, and quote shape.
    """
    path = "$"
    _check_fields(raw, EVIDENCE_FIELDS, "evidence", path)
    _record_type(raw, RecordType.EVIDENCE, path)
    evidence_id = _id(raw["evidence_id"], "evidence_id", path)
    source_id = _id(raw["source_id"], "source_id", path)
    source = PHASE3_SOURCES.get(source_id)
    if source is None:
        raise CitationError(
            f"unknown source_id {source_id!r}; allowed: "
            + ", ".join(sorted(PHASE3_SOURCES)),
            path=f"{path}.source_id",
        )
    source_kind = _enum(raw["source_kind"], SourceKind, "source_kind", path)
    if source_kind.value != source["kind"]:
        raise CitationError(
            f"source_id {source_id!r} is kind {source['kind']!r} but evidence "
            f"declares {source_kind.value!r}",
            path=f"{path}.source_kind",
        )
    content_sha256 = _sha256_hash(
        raw["content_sha256"], "content_sha256", path, CitationError
    )
    if content_sha256 != source["content_sha256"]:
        raise CitationError(
            f"content_sha256 {content_sha256[:16]}... does not match the frozen "
            f"source {source_id!r} (expected {source['content_sha256'][:16]}...)",
            path=f"{path}.content_sha256",
        )
    quote = _text(raw["quote"], "quote", path, MAX_QUOTE_LENGTH)
    if quote[0].isspace() or quote[-1].isspace():
        raise CitationError(
            "quote must not have leading or trailing whitespace",
            path=f"{path}.quote",
        )
    return {
        "type": RecordType.EVIDENCE.value,
        "evidence_id": evidence_id,
        "source_id": source_id,
        "source_kind": source_kind.value,
        "content_sha256": content_sha256,
        "locator": _locator(raw["locator"], source_kind, path),
        "quote": quote,
    }


def validate_citation(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a first-class CitationRecord, returning a normalized dict.

    Raises :class:`CitationError` on any violation. Fail-closed checks:
    unknown/missing fields, record type, id patterns for the citation and its
    claim/evidence references, support/conflict enumerated states, and the
    semantic version.
    """
    path = "$"
    _check_fields(raw, CITATION_FIELDS, "citation", path)
    _record_type(raw, RecordType.CITATION, path)
    return {
        "type": RecordType.CITATION.value,
        "id": _id(raw["id"], "id", path),
        "claim_id": _id(raw["claim_id"], "claim_id", path),
        "evidence_id": _id(raw["evidence_id"], "evidence_id", path),
        "support": _enum(raw["support"], SupportState, "support", path).value,
        "conflict": _enum(raw["conflict"], ConflictState, "conflict", path).value,
        "version": _version(raw["version"], "version", path),
    }


def validate_manifest(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a Phase 4 manifest, returning a normalized dict.

    Raises :class:`ManifestError` on any violation. Fail-closed checks:
    schema version, fixture metadata, and a sources mapping that must bind
    exactly the frozen Phase 3 source records (ids, kinds, paths, hashes).
    """
    path = "$"
    _check_fields(raw, MANIFEST_FIELDS, "manifest", path, ManifestError)
    schema = raw["schema_version"]
    if not isinstance(schema, str) or schema != SCHEMA_VERSION:
        raise ManifestError(
            f"unsupported schema_version {schema!r}; expected {SCHEMA_VERSION!r}",
            path=f"{path}.schema_version",
        )

    fixture_raw = raw["fixture"]
    if not isinstance(fixture_raw, Mapping):
        raise ManifestError("fixture must be a JSON object", path=f"{path}.fixture")
    _check_fields(
        fixture_raw, FIXTURE_FIELDS, "fixture", f"{path}.fixture", ManifestError
    )
    name = fixture_raw["name"]
    if not isinstance(name, str) or not name:
        raise ManifestError(
            "fixture.name must be a non-empty string", path=f"{path}.fixture.name"
        )
    file_path = _safe_path(fixture_raw["file"], "file", f"{path}.fixture")
    count = fixture_raw["count"]
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise ManifestError(
            "fixture.count must be a positive integer", path=f"{path}.fixture.count"
        )
    algorithm = fixture_raw["fingerprint_algorithm"]
    if not isinstance(algorithm, str) or algorithm != FINGERPRINT_ALGORITHM:
        raise ManifestError(
            f"unsupported fingerprint_algorithm {algorithm!r}; expected "
            f"{FINGERPRINT_ALGORITHM!r}",
            path=f"{path}.fixture.fingerprint_algorithm",
        )
    fingerprint = _sha256_hash(
        fixture_raw["fingerprint"], "fingerprint", f"{path}.fixture"
    )

    sources_raw = raw["sources"]
    if not isinstance(sources_raw, Mapping):
        raise ManifestError("sources must be a JSON object", path=f"{path}.sources")
    sources: dict[str, Any] = {}
    for source_id, entry in sources_raw.items():
        source_path = f"{path}.sources.{source_id}"
        _id(source_id, "source_id", source_path, ManifestError)
        if not isinstance(entry, Mapping):
            raise ManifestError("source entry must be a JSON object", path=source_path)
        _check_fields(entry, SOURCE_FIELDS, "source entry", source_path, ManifestError)
        sources[source_id] = {
            "kind": _enum(
                entry["kind"], SourceKind, "kind", source_path, ManifestError
            ).value,
            "path": _safe_path(entry["path"], "path", source_path),
            "hash": _sha256_hash(entry["hash"], "hash", source_path),
        }
    if not sources:
        raise ManifestError("sources must not be empty", path=f"{path}.sources")

    # The manifest must bind exactly the frozen Phase 3 source records.
    declared_ids = set(sources)
    frozen_ids = set(PHASE3_SOURCES)
    if declared_ids != frozen_ids:
        missing = sorted(frozen_ids - declared_ids)
        extra = sorted(declared_ids - frozen_ids)
        detail = []
        if missing:
            detail.append(f"missing {', '.join(missing)}")
        if extra:
            detail.append(f"unknown {', '.join(extra)}")
        raise ManifestError(
            "sources must bind exactly the frozen Phase 3 source records; "
            + "; ".join(detail),
            path=f"{path}.sources",
        )
    for source_id, entry in sources.items():
        frozen = PHASE3_SOURCES[source_id]
        if entry["kind"] != frozen["kind"]:
            raise ManifestError(
                f"source_id {source_id!r} is kind {frozen['kind']!r} in the "
                f"frozen Phase 3 manifest but declares {entry['kind']!r}",
                path=f"{path}.sources.{source_id}.kind",
            )
        if entry["path"] != frozen["path"]:
            raise ManifestError(
                f"source_id {source_id!r} has path {frozen['path']!r} in the "
                f"frozen Phase 3 manifest but declares {entry['path']!r}",
                path=f"{path}.sources.{source_id}.path",
            )
        if entry["hash"] != frozen["content_sha256"]:
            raise ManifestError(
                f"source_id {source_id!r} must bind the frozen content hash "
                f"{frozen['content_sha256'][:16]}... but declares "
                f"{entry['hash'][:16]}...",
                path=f"{path}.sources.{source_id}.hash",
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "fixture": {
            "name": name,
            "file": file_path,
            "count": count,
            "fingerprint_algorithm": FINGERPRINT_ALGORITHM,
            "fingerprint": fingerprint,
        },
        "sources": sources,
    }


def _sources_root() -> Path:
    """Absolute path to ``data/phase3/sources`` (repo root via this module)."""
    return Path(__file__).resolve().parents[2] / "data" / "phase3" / "sources"


def source_content_text(source_path: Path) -> str:
    """The locatable text of a Phase 3 source file.

    JSON sources expose their ``content`` field; markdown sources are read as
    raw text. Raises :class:`ManifestError` if the file cannot be read or its
    JSON shape is unexpected.
    """
    try:
        text = Path(source_path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(
            f"cannot read frozen source: {exc}", path="<source>"
        ) from exc
    if Path(source_path).suffix == ".json":
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ManifestError(
                f"frozen source is not valid JSON: {exc}", path="<source>"
            ) from exc
        if isinstance(obj, dict) and isinstance(obj.get("content"), str):
            return obj["content"]
        raise ManifestError(
            "frozen JSON source must have a string 'content' field",
            path="<source>",
        )
    return text


def fingerprint_sha256(path: Path) -> str:
    """sha256 hex digest of a file's bytes (the stable fixture fingerprint)."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_fixture(manifest_path: Path, fixture_path: Path) -> dict[str, Any]:
    """Load and strictly validate a citation fixture against its manifest.

    Returns ``{"manifest", "claims", "evidence", "citations"}``. Fail-closed
    checks: manifest validity and Phase 3 source binding, fixture fingerprint
    vs manifest, line count, per-line record validity, unique ids per record
    namespace, citation link references, frozen source content hashes vs the
    actual Phase 3 file bytes, and evidence quotes being exact bounded spans
    of their source content.
    """
    try:
        manifest_raw = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot read manifest: {exc}", path="<manifest>") from exc
    manifest = validate_manifest(manifest_raw)

    try:
        text = Path(fixture_path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"cannot read fixture: {exc}", path="<fixture>") from exc
    actual = hashlib.sha256(text.encode("utf-8")).hexdigest()
    expected = manifest["fixture"]["fingerprint"]
    if actual != expected:
        raise ManifestError(
            "fixture fingerprint mismatch: "
            f"file sha256 {actual} != manifest {expected}",
            path="fixture.fingerprint",
        )

    lines = text.splitlines()
    declared_count = manifest["fixture"]["count"]
    if len(lines) != declared_count:
        raise ManifestError(
            f"fixture has {len(lines)} line(s), manifest declares {declared_count}",
            path="fixture.count",
        )

    claims: dict[str, dict[str, Any]] = {}
    evidence: dict[str, dict[str, Any]] = {}
    citations: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        path = f"$[{index}]"
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CitationError(
                f"line {index + 1} is not valid JSON: {exc}", path=path
            ) from exc
        if not isinstance(raw, Mapping):
            raise CitationError(f"line {index + 1} must be a JSON object", path=path)
        record_type = _enum(raw.get("type"), RecordType, "type", path, CitationError)
        if record_type is RecordType.CLAIM:
            claim = validate_claim(raw)
            if claim["claim_id"] in claims:
                raise CitationError(
                    f"duplicate claim id {claim['claim_id']!r}", path=f"{path}.claim_id"
                )
            claims[claim["claim_id"]] = claim
        elif record_type is RecordType.EVIDENCE:
            item = validate_evidence(raw)
            if item["evidence_id"] in evidence:
                raise CitationError(
                    f"duplicate evidence id {item['evidence_id']!r}",
                    path=f"{path}.evidence_id",
                )
            evidence[item["evidence_id"]] = item
        else:
            citation = validate_citation(raw)
            if citation["id"] in {c["id"] for c in citations}:
                raise CitationError(
                    f"duplicate citation id {citation['id']!r}", path=f"{path}.id"
                )
            citations.append(citation)

    for citation in citations:
        if citation["claim_id"] not in claims:
            raise CitationError(
                f"citation {citation['id']!r} references unknown claim "
                f"{citation['claim_id']!r}",
                path="$.claim_id",
            )
        if citation["evidence_id"] not in evidence:
            raise CitationError(
                f"citation {citation['id']!r} references unknown evidence "
                f"{citation['evidence_id']!r}",
                path="$.evidence_id",
            )

    # Bind the manifest's source hashes to the actual frozen Phase 3 bytes and
    # load each source's text so quotes can be checked as exact spans.
    sources_root = _sources_root()
    content: dict[str, str] = {}
    for source_id, entry in manifest["sources"].items():
        source_file = sources_root / entry["path"]
        try:
            data = source_file.read_bytes()
        except OSError as exc:
            raise ManifestError(
                f"cannot read frozen source {entry['path']!r}: {exc}",
                path=f"sources.{source_id}.path",
            ) from exc
        byte_hash = hashlib.sha256(data).hexdigest()
        if byte_hash != entry["hash"]:
            raise ManifestError(
                f"frozen source {entry['path']!r} content hash mismatch: "
                f"file sha256 {byte_hash[:16]}... != manifest {entry['hash'][:16]}...",
                path=f"sources.{source_id}.hash",
            )
        content[source_id] = source_content_text(source_file)

    for item in evidence.values():
        source_text = content[item["source_id"]]
        if item["quote"] not in source_text:
            raise CitationError(
                f"evidence {item['evidence_id']!r} quote is not an exact span "
                f"of source {item['source_id']!r} content",
                path="$.evidence.quote",
            )
        if len(item["quote"]) >= len(source_text):
            raise CitationError(
                f"evidence {item['evidence_id']!r} quote is not a bounded span "
                f"(covers the entire source content)",
                path="$.evidence.quote",
            )

    return {
        "manifest": manifest,
        "claims": list(claims.values()),
        "evidence": list(evidence.values()),
        "citations": citations,
    }
