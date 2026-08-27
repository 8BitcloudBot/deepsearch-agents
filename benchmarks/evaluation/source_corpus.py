"""Versioned corpus loader with strict validation.

Loads ``data/phase3/sources/manifest.json`` plus each referenced source
file. The manifest is the index: it carries the identity and metadata of
every source. Structured source files (``web_snapshot`` and ``catalog``)
are JSON objects with exactly ``title``, ``origin``, ``captured_at`` and
``content``; the ``knowledge`` source is a plain UTF-8 Markdown file whose
metadata comes from the manifest.

Enforced invariants: paths stay under the manifest's sources root (no
absolute paths, no ``..``, no backslashes), source IDs are unique, kinds
are whitelisted, schema and unknown fields are rejected, every
``content_sha256`` matches the raw file bytes, all text is valid
UTF-8, at least one source must exist, and curated content must be
reviewed material: no credentials, executable instructions or unbounded
HTML. All failures raise :class:`ValueError` with a stable message.
"""

import codecs
import hashlib
import json
import re
from pathlib import Path

from benchmarks.evaluation.source_contracts import (
    VALID_SOURCE_KINDS,
    Corpus,
    SourceRecord,
)

DEFAULT_MANIFEST = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "phase3"
    / "sources"
    / "manifest.json"
)

_MANIFEST_FIELDS = frozenset({"corpus_id", "schema_version", "captured_at", "sources"})
_SOURCE_FIELDS = frozenset(
    {
        "source_id",
        "kind",
        "title",
        "origin",
        "captured_at",
        "path",
        "content_sha256",
    }
)
_RECORD_FIELDS = frozenset({"title", "origin", "captured_at", "content"})
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Forbidden unreviewed content: credentials, executable instructions and
# unbounded HTML never belong in curated versioned sources.
_FORBIDDEN_CONTENT_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=_-]{20,}", re.IGNORECASE),
    re.compile(
        r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|passwd|password|"
        r"secret|private[_-]?key)\b\s*[:=]\s*\S"
    ),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"<\s*(?:script|iframe|html)\b", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(
        r"(?m)^\s*(?:sudo|rm\s+-rf|curl|wget|pip\s+install|npm\s+install|"
        r"npx|bash|sh\s+-c|eval)\b"
    ),
    re.compile(r";\s*(?:rm\s+-rf|shutdown|mkfs|dd\s+if=)"),
)


def _require_fields(obj: dict, allowed: frozenset[str], label: str) -> None:
    unknown = set(obj) - allowed
    if unknown:
        raise ValueError(f"{label}: unknown field(s) {sorted(unknown)}")


def _require_non_empty_str(obj: dict, field: str, label: str) -> None:
    value = obj.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label}: {field} must be a non-empty string")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode_utf8(data: bytes, message: str) -> str:
    """Decode bytes as strict UTF-8 text.

    ``json.loads`` would auto-detect UTF-16/UTF-32 (and strip a UTF-8
    BOM) from bytes, silently violating the UTF-8-only contract, so text
    is decoded explicitly first and anything else is rejected.
    """
    if data.startswith(codecs.BOM_UTF8):
        raise ValueError(message)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(message) from exc


def _check_content_safety(content: str, label: str) -> None:
    """Reject unreviewed content: credentials, exec, unbounded HTML."""
    if not content.strip():
        raise ValueError(f"{label}: content must be a non-empty string")
    for pattern in _FORBIDDEN_CONTENT_PATTERNS:
        if pattern.search(content):
            raise ValueError(f"{label}: forbidden unreviewed content")


def _read_source_record(
    fpath: Path, entry: dict, data: bytes, label: str
) -> tuple[str, str, str, str]:
    """Return (content, title, origin, captured_at) for one source file."""
    if entry["kind"] == "knowledge":
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{label}: content is not valid UTF-8") from exc
        _check_content_safety(text, label)
        return (
            text,
            entry["title"],
            entry["origin"],
            entry["captured_at"],
        )
    text = _decode_utf8(data, f"{label}: content is not valid UTF-8")
    try:
        record = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}: content is not valid JSON") from exc
    if not isinstance(record, dict):
        raise ValueError(f"{label}: content must be a JSON object")
    _require_fields(record, _RECORD_FIELDS, label)
    _require_non_empty_str(record, "title", label)
    _require_non_empty_str(record, "origin", label)
    _require_non_empty_str(record, "captured_at", label)
    if not isinstance(record["content"], str):
        raise ValueError(f"{label}: content must be a string")
    _check_content_safety(record["content"], label)
    for field in ("title", "origin", "captured_at"):
        if record[field] != entry[field]:
            raise ValueError(
                f"{label}: metadata mismatch for {entry['source_id']!r}: "
                f"{field} differs from manifest"
            )
    return (
        record["content"],
        entry["title"],
        entry["origin"],
        entry["captured_at"],
    )


def load_corpus(manifest_path: str | Path | None = None) -> Corpus:
    """Load and validate the versioned research corpus.

    ``manifest_path`` defaults to the curated
    ``data/phase3/sources/manifest.json``.
    """
    manifest = Path(manifest_path) if manifest_path else DEFAULT_MANIFEST
    if not manifest.is_file():
        raise ValueError(f"manifest not found: {manifest}")
    root = manifest.resolve().parent

    text = _decode_utf8(manifest.read_bytes(), "manifest is not valid UTF-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("manifest is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("manifest must be a JSON object")
    _require_fields(payload, _MANIFEST_FIELDS, "manifest")
    _require_non_empty_str(payload, "corpus_id", "manifest")
    _require_non_empty_str(payload, "captured_at", "manifest")
    if payload.get("schema_version") != 1:
        raise ValueError(
            f"manifest: unsupported schema_version {payload.get('schema_version')!r}"
        )
    sources = payload.get("sources")
    if not isinstance(sources, list):
        raise ValueError("manifest: sources must be a list")
    if not sources:
        raise ValueError("manifest: sources must not be empty")

    records: list[SourceRecord] = []
    seen: set[str] = set()
    for i, entry in enumerate(sources):
        label = f"sources[{i}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{label}: must be a JSON object")
        _require_fields(entry, _SOURCE_FIELDS, label)
        _require_non_empty_str(entry, "source_id", label)
        source_id = entry["source_id"]
        if source_id in seen:
            raise ValueError(f"duplicate source_id: {source_id!r}")
        seen.add(source_id)
        _require_non_empty_str(entry, "kind", label)
        kind = entry["kind"]
        if kind not in VALID_SOURCE_KINDS:
            raise ValueError(f"{label}: unknown kind {kind!r}")
        _require_non_empty_str(entry, "title", label)
        _require_non_empty_str(entry, "origin", label)
        _require_non_empty_str(entry, "captured_at", label)
        expected_sha = entry.get("content_sha256")
        if not isinstance(expected_sha, str) or not _SHA256_RE.fullmatch(expected_sha):
            raise ValueError(f"{label}: invalid content_sha256")
        _require_non_empty_str(entry, "path", label)
        rel = Path(entry["path"])
        if rel.is_absolute() or ".." in rel.parts or "\\" in str(rel):
            raise ValueError(f"{label}: path escapes sources root: {entry['path']!r}")
        fpath = (root / rel).resolve()
        if not fpath.is_relative_to(root):
            raise ValueError(f"{label}: path escapes sources root: {entry['path']!r}")
        if not fpath.is_file():
            raise ValueError(f"{label}: file not found: {entry['path']!r}")

        data = fpath.read_bytes()
        if _sha256_bytes(data) != expected_sha:
            raise ValueError(f"{label}: content_sha256 mismatch for {source_id!r}")

        content, title, origin, captured_at = _read_source_record(
            fpath, entry, data, label
        )
        records.append(
            SourceRecord(
                source_id=source_id,
                kind=kind,
                title=title,
                origin=origin,
                captured_at=captured_at,
                content=content,
                content_sha256=expected_sha,
            )
        )

    return Corpus(
        corpus_id=payload["corpus_id"],
        schema_version=payload["schema_version"],
        captured_at=payload["captured_at"],
        sources=tuple(records),
    )
