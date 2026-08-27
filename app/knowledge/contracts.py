"""Stable, vendor-neutral contracts for indexing and retrieving evidence chunks."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, Protocol
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
_FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")


def _identifier(value: str, field: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"{field} must be a safe identifier")
    folded = value.casefold()
    if any(token in folded for token in ("secret", "password", "api_key")):
        raise ValueError(f"{field} contains a secret-like value")
    return value


def _text(value: str, field: str, *, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    value = value.strip()
    if len(value) > max_length or any(
        ord(char) < 0x20 and char not in "\n\t" for char in value
    ):
        raise ValueError(f"{field} is invalid")
    return value


def _version(value: str) -> str:
    value = _text(value, "version", max_length=128)
    if not _SEMVER_RE.fullmatch(value):
        raise ValueError("version must be semantic")
    return value


def _source_uri(value: str | None) -> str | None:
    if value is None:
        return None
    value = _text(value, "source_uri", max_length=512)
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("source_uri must be an http(s) URL")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError("source_uri contains unsafe components")
    return value


def _fingerprint(value: object) -> str:
    canonical = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EmbeddingDescriptor:
    provider: str
    model: str
    version: str
    dimension: int
    query_prefix: str = ""
    document_prefix: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", _identifier(self.provider, "provider"))
        object.__setattr__(self, "model", _text(self.model, "model", max_length=200))
        object.__setattr__(
            self, "version", _text(self.version, "version", max_length=128)
        )
        if (
            isinstance(self.dimension, bool)
            or not isinstance(self.dimension, int)
            or self.dimension < 1
        ):
            raise ValueError("dimension must be a positive integer")
        for field in ("query_prefix", "document_prefix"):
            value = getattr(self, field)
            if (
                not isinstance(value, str)
                or len(value) > 64
                or any(ord(char) < 0x20 for char in value)
            ):
                raise ValueError(f"{field} is invalid")

    def fingerprint_payload(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "version": self.version,
            "dimension": self.dimension,
            "query_prefix": self.query_prefix,
            "document_prefix": self.document_prefix,
        }


@dataclass(frozen=True)
class KnowledgeIndexSpec:
    collection_id: str
    embedding: EmbeddingDescriptor
    distance: Literal["cosine", "dot", "euclid"] = "cosine"
    chunking_version: str = "v1"

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "collection_id", _identifier(self.collection_id, "collection_id")
        )
        if self.distance not in {"cosine", "dot", "euclid"}:
            raise ValueError("distance is unsupported")
        object.__setattr__(
            self,
            "chunking_version",
            _text(self.chunking_version, "chunking_version", max_length=128),
        )

    @property
    def embedding_fingerprint(self) -> str:
        return _fingerprint(self.embedding.fingerprint_payload())

    @property
    def index_fingerprint(self) -> str:
        return _fingerprint(
            {
                "collection_id": self.collection_id,
                "embedding_fingerprint": self.embedding_fingerprint,
                "distance": self.distance,
                "chunking_version": self.chunking_version,
            }
        )

    @property
    def physical_collection_name(self) -> str:
        return f"{self.collection_id}-{self.index_fingerprint[:12]}"


@dataclass(frozen=True)
class KnowledgeDocumentChunk:
    chunk_id: str
    content: str
    section_path: str | None = None
    source_uri: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "chunk_id", _identifier(self.chunk_id, "chunk_id"))
        object.__setattr__(
            self, "content", _text(self.content, "content", max_length=65536)
        )
        if self.section_path is not None:
            object.__setattr__(
                self,
                "section_path",
                _text(self.section_path, "section_path", max_length=512),
            )
        object.__setattr__(self, "source_uri", _source_uri(self.source_uri))


@dataclass(frozen=True)
class KnowledgeDocument:
    collection_id: str
    document_id: str
    title: str
    version: str
    chunks: tuple[KnowledgeDocumentChunk, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "collection_id", _identifier(self.collection_id, "collection_id")
        )
        object.__setattr__(
            self, "document_id", _identifier(self.document_id, "document_id")
        )
        object.__setattr__(self, "title", _text(self.title, "title", max_length=200))
        object.__setattr__(self, "version", _version(self.version))
        if not self.chunks or len({chunk.chunk_id for chunk in self.chunks}) != len(
            self.chunks
        ):
            raise ValueError("chunks must be non-empty with unique identities")


@dataclass(frozen=True)
class KnowledgeChunk:
    collection_id: str
    document_id: str
    chunk_id: str
    title: str
    content: str
    score: float
    version: str
    source_uri: str | None = None
    section_path: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "collection_id", _identifier(self.collection_id, "collection_id")
        )
        object.__setattr__(
            self, "document_id", _identifier(self.document_id, "document_id")
        )
        object.__setattr__(self, "chunk_id", _identifier(self.chunk_id, "chunk_id"))
        object.__setattr__(self, "title", _text(self.title, "title", max_length=200))
        object.__setattr__(
            self, "content", _text(self.content, "content", max_length=65536)
        )
        if (
            isinstance(self.score, bool)
            or not isinstance(self.score, int | float)
            or not math.isfinite(self.score)
        ):
            raise ValueError("score must be finite")
        object.__setattr__(self, "score", float(self.score))
        object.__setattr__(self, "version", _version(self.version))
        object.__setattr__(self, "source_uri", _source_uri(self.source_uri))
        if self.section_path is not None:
            object.__setattr__(
                self,
                "section_path",
                _text(self.section_path, "section_path", max_length=512),
            )


@dataclass(frozen=True)
class IndexReport:
    collection_id: str
    physical_collection_name: str
    index_fingerprint: str
    indexed_chunks: int
    skipped_chunks: int


class KnowledgeUnavailable(RuntimeError):  # noqa: N818 - public contract name
    code = "knowledge-unavailable"

    def as_limitation(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self)}


class EmbeddingAdapter(Protocol):
    descriptor: EmbeddingDescriptor

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class KnowledgeRetriever(Protocol):
    def search(
        self,
        query: str,
        *,
        collection_id: str | None = None,
        limit: int = 8,
        document_version: str | None = None,
    ) -> tuple[KnowledgeChunk, ...]: ...


class KnowledgeIndexer(Protocol):
    def index_documents(
        self, documents: Sequence[KnowledgeDocument]
    ) -> IndexReport: ...


def stable_point_id(collection_id: str, document_id: str, chunk_id: str) -> str:
    identity = "|".join(
        (
            _identifier(collection_id, "collection_id"),
            _identifier(document_id, "document_id"),
            _identifier(chunk_id, "chunk_id"),
        )
    )
    return str(uuid5(NAMESPACE_URL, f"deepsearch-knowledge:{identity}"))


def resolve_knowledge_index_path(configured: str, *, runtime_root: Path) -> Path:
    configured = _text(configured, "knowledge index path", max_length=255)
    path = PurePosixPath(configured.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or configured.startswith("~"):
        raise ValueError("knowledge index path must be a safe relative path")
    root = runtime_root.resolve()
    resolved = (root / Path(*path.parts)).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("knowledge index path escapes the runtime root")
    return resolved


def validate_fingerprint(value: object, field: str = "fingerprint") -> str:
    if not isinstance(value, str) or not _FINGERPRINT_RE.fullmatch(value):
        raise ValueError(f"{field} is invalid")
    return value
