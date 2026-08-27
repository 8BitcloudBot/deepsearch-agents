"""Strict loader for versioned evaluation datasets (JSONL + registry).

``data/phase3/datasets/manifest.json`` is the strict multi-dataset
registry: a top-level ``datasets`` list, one entry per frozen dataset
(dataset ID, schema version, bound corpus ID, exact case count, the
relative JSONL file name and that file's SHA-256). Every JSONL line is
one :class:`EvaluationCase` with a fixed schema; case IDs must be unique
and strictly sorted, the split must match the case-ID prefix, and every
``allowed_source_ids`` entry must exist in the bound corpus.

Every registry entry is validated fully — unknown or missing fields,
duplicate dataset IDs, invalid split or difficulty, unknown source IDs,
manifest/corpus/count/hash mismatch, path escape, non-UTF-8 text and
malformed JSON lines all raise :class:`ValueError` with a stable
message. Selection is deterministic: :func:`load_dataset` returns the
frozen default ``seed-10-v1``; :func:`load_dataset_by_name` resolves a
CLI alias (``seed-10``/``dev-40``) or an exact frozen dataset ID
(``seed-10-v1``/``dev-40-v1``) and rejects unknown names.
"""

import codecs
import hashlib
import json
import re
from pathlib import Path

from benchmarks.evaluation.contracts import (
    CASE_ID_RE,
    VALID_DIFFICULTIES,
    VALID_SPLITS,
    Dataset,
    EvaluationCase,
)
from benchmarks.evaluation.source_contracts import Corpus
from benchmarks.evaluation.source_corpus import load_corpus

DEFAULT_DATASET_MANIFEST = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "phase3"
    / "datasets"
    / "manifest.json"
)

# Default frozen dataset returned by load_dataset(); registry selection is
# deterministic by this exact ID (P3-3, preserved by P3-5).
DEFAULT_DATASET_ID = "seed-10-v1"

# CLI dataset names -> frozen dataset IDs (P3-3: seed-10; P3-5 adds dev-40
# behind the same selection path).
DATASET_ALIASES: dict[str, str] = {
    "seed-10": "seed-10-v1",
    "dev-40": "dev-40-v1",
}

_REGISTRY_FIELDS = frozenset({"datasets"})
_ENTRY_FIELDS = frozenset(
    {"dataset_id", "schema_version", "corpus_id", "case_count", "file", "file_sha256"}
)
_CASE_FIELDS = frozenset(
    {
        "case_id",
        "split",
        "question",
        "expected_topics",
        "allowed_source_ids",
        "difficulty",
    }
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _require_fields(obj: dict, allowed: frozenset[str], label: str) -> None:
    unknown = set(obj) - allowed
    if unknown:
        raise ValueError(f"{label}: unknown field(s) {sorted(unknown)}")


def _require_non_empty_str(obj: dict, field: str, label: str) -> None:
    value = obj.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label}: {field} must be a non-empty string")


def _require_string_list(obj: dict, field: str, label: str) -> tuple[str, ...]:
    value = obj.get(field)
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise ValueError(f"{label}: {field} must be a non-empty list of strings")
    return tuple(value)


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


def _validate_case(line: dict, corpus: Corpus, lineno: int) -> EvaluationCase:
    label = f"line {lineno}"
    _require_fields(line, _CASE_FIELDS, label)
    _require_non_empty_str(line, "case_id", label)
    case_id = line["case_id"]
    match = CASE_ID_RE.fullmatch(case_id)
    if match is None:
        raise ValueError(f"{label}: invalid case_id format {case_id!r}")
    prefix = match.group(1)
    _require_non_empty_str(line, "split", label)
    split = line["split"]
    if split not in VALID_SPLITS:
        raise ValueError(f"{label}: split must be one of {sorted(VALID_SPLITS)}")
    if prefix != split:
        raise ValueError(
            f"{label}: split {split!r} does not match case_id prefix {prefix!r}"
        )
    _require_non_empty_str(line, "question", label)
    topics = _require_string_list(line, "expected_topics", label)
    allowed = _require_string_list(line, "allowed_source_ids", label)
    _require_non_empty_str(line, "difficulty", label)
    difficulty = line["difficulty"]
    if difficulty not in VALID_DIFFICULTIES:
        raise ValueError(
            f"{label}: difficulty must be one of {sorted(VALID_DIFFICULTIES)}"
        )
    corpus_ids = {source.source_id for source in corpus.sources}
    unknown = [sid for sid in allowed if sid not in corpus_ids]
    if unknown:
        raise ValueError(
            f"{label}: unknown source_id {unknown[0]!r} in allowed_source_ids"
        )
    return EvaluationCase(
        case_id=case_id,
        split=split,
        question=line["question"],
        expected_topics=topics,
        allowed_source_ids=allowed,
        difficulty=difficulty,
    )


def _validate_registry_entry(entry: dict, corpus: Corpus, root: Path) -> Dataset:
    """Validate one registry entry (fields, file, hash, cases, count)."""
    label = f"dataset manifest entry {entry.get('dataset_id', '?')!r}"
    _require_fields(entry, _ENTRY_FIELDS, label)
    _require_non_empty_str(entry, "dataset_id", label)
    _require_non_empty_str(entry, "corpus_id", label)
    if entry.get("schema_version") != 1:
        raise ValueError(
            f"{label}: unsupported schema_version {entry.get('schema_version')!r}"
        )
    case_count = entry.get("case_count")
    if (
        not isinstance(case_count, int)
        or isinstance(case_count, bool)
        or case_count < 0
    ):
        raise ValueError(f"{label}: case_count must be a non-negative integer")
    _require_non_empty_str(entry, "file", label)
    rel = Path(entry["file"])
    if rel.is_absolute() or ".." in rel.parts or "\\" in str(rel):
        raise ValueError(f"{label}: file path escapes dataset root: {entry['file']!r}")
    fpath = (root / rel).resolve()
    if not fpath.is_relative_to(root):
        raise ValueError(f"{label}: file path escapes dataset root: {entry['file']!r}")
    expected_sha = entry.get("file_sha256")
    if not isinstance(expected_sha, str) or not _SHA256_RE.fullmatch(expected_sha):
        raise ValueError(f"{label}: invalid file_sha256")
    if not fpath.is_file():
        raise ValueError(f"{label}: file not found: {entry['file']!r}")

    if entry["corpus_id"] != corpus.corpus_id:
        raise ValueError(
            f"{label}: corpus_id "
            f"{entry['corpus_id']!r} does not match corpus {corpus.corpus_id!r}"
        )

    data = fpath.read_bytes()
    if _sha256_bytes(data) != expected_sha:
        raise ValueError(f"{label}: file_sha256 mismatch for {entry['file']!r}")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{entry['file']}: content is not valid UTF-8") from exc

    cases: list[EvaluationCase] = []
    seen: set[str] = set()
    previous_id: str | None = None
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"{entry['file']} line {lineno}: blank line")
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{entry['file']} line {lineno}: not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"{entry['file']} line {lineno}: must be a JSON object")
        case = _validate_case(parsed, corpus, lineno)
        if case.case_id in seen:
            raise ValueError(
                f"{entry['file']} line {lineno}: duplicate case_id {case.case_id!r}"
            )
        seen.add(case.case_id)
        if previous_id is not None and case.case_id <= previous_id:
            raise ValueError(
                f"{entry['file']} line {lineno}: case_id not sorted "
                f"({case.case_id!r} after {previous_id!r})"
            )
        previous_id = case.case_id
        cases.append(case)

    if len(cases) != case_count:
        raise ValueError(
            f"{label}: case_count "
            f"{case_count} does not match {len(cases)} loaded case(s)"
        )

    return Dataset(
        dataset_id=entry["dataset_id"],
        schema_version=entry["schema_version"],
        corpus_id=entry["corpus_id"],
        file=entry["file"],
        file_sha256=expected_sha,
        cases=tuple(cases),
    )


def _load_registry(
    manifest_path: str | Path | None = None,
    corpus: Corpus | None = None,
) -> list[Dataset]:
    """Parse and strictly validate the whole dataset registry.

    ``manifest_path`` defaults to ``data/phase3/datasets/manifest.json``;
    ``corpus`` defaults to the curated ``data/phase3/sources`` corpus.
    Every entry is validated (fields, duplicates, path, hash, UTF-8,
    cases, count) so a malformed entry is rejected even when it is not
    the one being selected.
    """
    manifest = Path(manifest_path) if manifest_path else DEFAULT_DATASET_MANIFEST
    if not manifest.is_file():
        raise ValueError(f"dataset manifest not found: {manifest}")
    root = manifest.resolve().parent

    text = _decode_utf8(manifest.read_bytes(), "dataset manifest is not valid UTF-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("dataset manifest is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("dataset manifest must be a JSON object")
    _require_fields(payload, _REGISTRY_FIELDS, "dataset manifest")
    entries = payload.get("datasets")
    if not isinstance(entries, list) or not entries:
        raise ValueError("dataset manifest: datasets must be a non-empty list")

    if corpus is None:
        corpus = load_corpus()

    seen_ids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(
                "dataset manifest: every datasets entry must be a JSON object"
            )
        entry_id = entry.get("dataset_id")
        if isinstance(entry_id, str) and entry_id in seen_ids:
            raise ValueError(f"dataset manifest: duplicate registry entry {entry_id!r}")
        if isinstance(entry_id, str):
            seen_ids.add(entry_id)

    return [_validate_registry_entry(entry, corpus, root) for entry in entries]


def load_dataset(
    manifest_path: str | Path | None = None,
    corpus: Corpus | None = None,
) -> Dataset:
    """Load and validate the default frozen dataset (``seed-10-v1``).

    The whole registry is validated; the frozen default entry is then
    selected deterministically by :data:`DEFAULT_DATASET_ID`.
    """
    for dataset in _load_registry(manifest_path, corpus):
        if dataset.dataset_id == DEFAULT_DATASET_ID:
            return dataset
    raise ValueError(
        f"dataset manifest: default dataset {DEFAULT_DATASET_ID!r} is not registered"
    )


def load_dataset_by_name(name: str) -> Dataset:
    """Load the frozen dataset selected by a CLI name (e.g. ``dev-40``).

    The name may be a registered alias (``seed-10``/``dev-40``) or the
    exact frozen dataset ID (``seed-10-v1``/``dev-40-v1``). Unknown
    names raise :class:`ValueError` with a stable message.
    """
    dataset_id = DATASET_ALIASES.get(name, name)
    datasets = _load_registry()
    for dataset in datasets:
        if dataset.dataset_id == dataset_id:
            return dataset
    known = ", ".join(sorted(dataset.dataset_id for dataset in datasets)) or "none"
    raise ValueError(f"unknown dataset {name!r} (known: {known})")
