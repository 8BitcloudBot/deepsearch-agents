"""Qdrant Local path-mode index with explicit fingerprint ownership."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from app.knowledge.contracts import (
    EmbeddingAdapter,
    IndexReport,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIndexSpec,
    KnowledgeUnavailable,
    stable_point_id,
    validate_fingerprint,
)

_MANIFEST_NAME = "deepsearch-knowledge-manifest.json"
_REQUIRED_PAYLOAD = frozenset(
    {
        "collection_id",
        "document_id",
        "chunk_id",
        "title",
        "version",
        "content",
        "content_sha256",
        "embedding_fingerprint",
        "index_fingerprint",
    }
)


class QdrantLocalKnowledgeIndex:
    """Explicit offline indexer and read-only-at-query knowledge retriever."""

    def __init__(
        self,
        path: Path,
        spec: KnowledgeIndexSpec,
        embedder: EmbeddingAdapter,
    ) -> None:
        self._path = path
        self._spec = spec
        self._embedder = embedder
        if embedder.descriptor != spec.embedding:
            raise ValueError("embedding descriptor does not match index fingerprint")
        self._check_manifest()
        self._client: Any = None

    def _check_manifest(self) -> None:
        manifest_path = self._path / _MANIFEST_NAME
        if not manifest_path.exists():
            return
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("knowledge index fingerprint manifest is invalid") from exc
        if (
            not isinstance(manifest, dict)
            or manifest.get("collection_id") != self._spec.collection_id
            or manifest.get("index_fingerprint") != self._spec.index_fingerprint
            or manifest.get("physical_collection_name")
            != self._spec.physical_collection_name
        ):
            raise ValueError("knowledge index fingerprint does not match configuration")

    def _write_manifest(self) -> None:
        self._path.mkdir(parents=True, exist_ok=True)
        manifest = {
            "collection_id": self._spec.collection_id,
            "physical_collection_name": self._spec.physical_collection_name,
            "embedding_fingerprint": self._spec.embedding_fingerprint,
            "index_fingerprint": self._spec.index_fingerprint,
        }
        (self._path / _MANIFEST_NAME).write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

    def _get_client(self):
        if self._client is None:
            try:
                from qdrant_client import QdrantClient
            except ImportError as exc:
                raise KnowledgeUnavailable(
                    "local knowledge adapter is unavailable"
                ) from exc
            self._path.mkdir(parents=True, exist_ok=True)
            self._client = QdrantClient(path=str(self._path))
        return self._client

    def _collection_exists(self) -> bool:
        client = self._get_client()
        return client.collection_exists(self._spec.physical_collection_name)

    def _ensure_collection(self) -> None:
        if self._collection_exists():
            return
        from qdrant_client.models import Distance, VectorParams

        distance = {
            "cosine": Distance.COSINE,
            "dot": Distance.DOT,
            "euclid": Distance.EUCLID,
        }[self._spec.distance]
        self._get_client().create_collection(
            collection_name=self._spec.physical_collection_name,
            vectors_config=VectorParams(
                size=self._spec.embedding.dimension,
                distance=distance,
            ),
        )

    def index_documents(self, documents: Sequence[KnowledgeDocument]) -> IndexReport:
        from qdrant_client.models import PointStruct

        documents = tuple(documents)
        document_ids: set[str] = set()
        for document in documents:
            if document.collection_id != self._spec.collection_id:
                raise ValueError("document collection_id is not allowed")
            if document.document_id in document_ids:
                raise ValueError("document identities must be unique per indexing call")
            document_ids.add(document.document_id)
        self._ensure_collection()
        self._write_manifest()

        skipped = 0
        client = self._get_client()
        pending: list[tuple[str, dict[str, object], str]] = []
        stale_by_document: list[list[str]] = []
        for document in documents:
            existing = self._document_points(document.document_id)
            supplied_ids: set[str] = set()
            for chunk in document.chunks:
                point_id = stable_point_id(
                    document.collection_id, document.document_id, chunk.chunk_id
                )
                supplied_ids.add(point_id)
                payload = self._point_payload(document, chunk)
                if existing.get(point_id) == payload:
                    skipped += 1
                    continue
                pending.append((point_id, payload, chunk.content))
            stale_by_document.append(
                sorted(
                    point_id for point_id in existing if point_id not in supplied_ids
                )
            )

        points: list[PointStruct] = []
        if pending:
            vectors = self._embedder.embed_documents(
                [content for _, _, content in pending]
            )
            if len(vectors) != len(pending) or any(
                len(vector) != self._spec.embedding.dimension for vector in vectors
            ):
                raise ValueError("embedding dimension does not match index fingerprint")
            points = [
                PointStruct(id=point_id, vector=vector, payload=payload)
                for (point_id, payload, _), vector in zip(pending, vectors, strict=True)
            ]

        if points:
            client.upsert(
                collection_name=self._spec.physical_collection_name,
                points=points,
                wait=True,
            )
        for stale_ids in stale_by_document:
            if stale_ids:
                client.delete(
                    collection_name=self._spec.physical_collection_name,
                    points_selector=stale_ids,
                    wait=True,
                )

        return IndexReport(
            collection_id=self._spec.collection_id,
            physical_collection_name=self._spec.physical_collection_name,
            index_fingerprint=self._spec.index_fingerprint,
            indexed_chunks=len(points),
            skipped_chunks=skipped,
        )

    def _document_points(self, document_id: str) -> dict[str, dict[str, object]]:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        document_filter = Filter(
            must=[
                FieldCondition(
                    key="collection_id",
                    match=MatchValue(value=self._spec.collection_id),
                ),
                FieldCondition(key="document_id", match=MatchValue(value=document_id)),
            ]
        )
        points: dict[str, dict[str, object]] = {}
        offset = None
        while True:
            records, offset = self._get_client().scroll(
                collection_name=self._spec.physical_collection_name,
                scroll_filter=document_filter,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for record in records:
                if isinstance(record.payload, dict):
                    points[str(record.id)] = record.payload
            if offset is None:
                return points

    def _point_payload(
        self, document: KnowledgeDocument, chunk: Any
    ) -> dict[str, object]:
        return {
            "collection_id": document.collection_id,
            "document_id": document.document_id,
            "chunk_id": chunk.chunk_id,
            "title": document.title,
            "version": document.version,
            "section_path": chunk.section_path,
            "source_uri": chunk.source_uri,
            "content": chunk.content,
            "content_sha256": _content_sha256(chunk.content),
            "embedding_fingerprint": self._spec.embedding_fingerprint,
            "index_fingerprint": self._spec.index_fingerprint,
        }

    def search(
        self,
        query: str,
        *,
        collection_id: str | None = None,
        limit: int = 8,
        document_version: str | None = None,
    ) -> tuple[KnowledgeChunk, ...]:
        if collection_id is not None and collection_id != self._spec.collection_id:
            raise ValueError("collection_id is not allowed")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 20
        ):
            raise ValueError("limit must be between 1 and 20")
        try:
            collection_exists = self._path.exists() and self._collection_exists()
        except Exception as exc:
            raise KnowledgeUnavailable("knowledge collection is unavailable") from exc
        if not collection_exists:
            raise KnowledgeUnavailable("knowledge collection is not indexed")

        try:
            vector = self._embedder.embed_query(query.strip())
        except Exception as exc:
            raise KnowledgeUnavailable(
                "knowledge embedding model is unavailable"
            ) from exc
        if len(vector) != self._spec.embedding.dimension:
            raise KnowledgeUnavailable("knowledge embedding model is unavailable")
        client = self._get_client()
        try:
            points = client.query_points(
                collection_name=self._spec.physical_collection_name,
                query=vector,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            ).points
        except Exception as exc:
            raise KnowledgeUnavailable("knowledge collection is unavailable") from exc

        chunks: list[KnowledgeChunk] = []
        for point in points:
            payload = point.payload
            try:
                chunk = self._chunk_from_payload(payload, float(point.score))
            except (TypeError, ValueError):
                continue
            if document_version is None or chunk.version == document_version:
                chunks.append(chunk)
        chunks.sort(key=lambda item: (-item.score, item.document_id, item.chunk_id))
        return tuple(chunks)

    def _chunk_from_payload(
        self, payload: Mapping[str, object] | None, score: float
    ) -> KnowledgeChunk:
        if not isinstance(payload, Mapping) or not _REQUIRED_PAYLOAD <= payload.keys():
            raise ValueError("knowledge chunk metadata is invalid")
        fingerprint = validate_fingerprint(
            payload.get("index_fingerprint"), "index fingerprint"
        )
        if fingerprint != self._spec.index_fingerprint:
            raise ValueError("knowledge chunk fingerprint mismatch")
        embedding_fingerprint = validate_fingerprint(
            payload.get("embedding_fingerprint"), "embedding fingerprint"
        )
        if embedding_fingerprint != self._spec.embedding_fingerprint:
            raise ValueError("knowledge chunk embedding fingerprint mismatch")
        if payload.get("collection_id") != self._spec.collection_id:
            raise ValueError("knowledge chunk collection mismatch")
        content = payload.get("content")
        if not isinstance(content, str) or payload.get(
            "content_sha256"
        ) != _content_sha256(content):
            raise ValueError("knowledge chunk content fingerprint mismatch")
        return KnowledgeChunk(
            collection_id=str(payload["collection_id"]),
            document_id=str(payload["document_id"]),
            chunk_id=str(payload["chunk_id"]),
            title=str(payload["title"]),
            content=content,
            score=score,
            version=str(payload["version"]),
            source_uri=(
                str(payload["source_uri"]) if payload.get("source_uri") else None
            ),
            section_path=(
                str(payload["section_path"]) if payload.get("section_path") else None
            ),
        )


def _content_sha256(content: str) -> str:
    import hashlib

    return hashlib.sha256(content.encode("utf-8")).hexdigest()
