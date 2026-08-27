"""Phase 3 evaluation contracts for versioned source corpora."""

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

SourceKind = Literal["web_snapshot", "catalog", "knowledge"]

VALID_SOURCE_KINDS: frozenset[str] = frozenset({"web_snapshot", "catalog", "knowledge"})


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    kind: SourceKind
    title: str
    origin: str
    captured_at: str
    content: str
    content_sha256: str


@dataclass(frozen=True)
class Corpus:
    corpus_id: str
    schema_version: int
    captured_at: str
    sources: tuple[SourceRecord, ...]


def corpus_sha256(corpus: Corpus) -> str:
    """Reproducible SHA-256 fingerprint of a validated corpus.

    Canonical JSON over the corpus identity plus every source record's
    manifest metadata and content hash, ordered by ``source_id``. The
    fingerprint is stable across processes and Python versions, so the
    same frozen corpus always hashes identically.
    """
    payload = {
        "corpus_id": corpus.corpus_id,
        "schema_version": corpus.schema_version,
        "captured_at": corpus.captured_at,
        "sources": [
            {
                "source_id": source.source_id,
                "kind": source.kind,
                "title": source.title,
                "origin": source.origin,
                "captured_at": source.captured_at,
                "content_sha256": source.content_sha256,
            }
            for source in sorted(corpus.sources, key=lambda s: s.source_id)
        ],
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
