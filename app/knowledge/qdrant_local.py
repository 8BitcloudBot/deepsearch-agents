"""Qdrant Local path-mode index with explicit fingerprint ownership."""

from __future__ import annotations

import json
import math
import re
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

    @staticmethod
    def check_readiness(path: Path, spec: KnowledgeIndexSpec) -> tuple[bool, str]:
        """Inspect an existing index without creating storage or loading embeddings."""
        if not path.is_dir():
            return False, "knowledge index is unavailable"
        manifest_path = path / _MANIFEST_NAME
        if not manifest_path.is_file():
            return False, "knowledge index manifest is unavailable"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False, "knowledge index manifest is invalid"
        if (
            not isinstance(manifest, dict)
            or manifest.get("collection_id") != spec.collection_id
            or manifest.get("index_fingerprint") != spec.index_fingerprint
            or manifest.get("physical_collection_name") != spec.physical_collection_name
        ):
            return False, "knowledge index fingerprint does not match configuration"
        try:
            from qdrant_client import QdrantClient

            client = QdrantClient(path=str(path))
            exists = client.collection_exists(spec.physical_collection_name)
            points_count = (
                client.get_collection(spec.physical_collection_name).points_count
                if exists
                else 0
            )
            client.close()
        except Exception:
            return False, "knowledge collection is unavailable"
        if not exists:
            return False, "knowledge collection is unavailable"
        if not points_count:
            return False, "knowledge collection is empty"
        return True, "knowledge collection is ready"

    def __init__(
        self,
        path: Path,
        spec: KnowledgeIndexSpec,
        embedder: EmbeddingAdapter,
        *,
        min_score: float | None = None,
    ) -> None:
        self._path = path
        self._spec = spec
        self._embedder = embedder
        if embedder.descriptor != spec.embedding:
            raise ValueError("embedding descriptor does not match index fingerprint")
        if min_score is not None and (
            isinstance(min_score, bool)
            or not isinstance(min_score, int | float)
            or not math.isfinite(min_score)
            or not 0.0 <= min_score <= 1.0
        ):
            raise ValueError("minimum knowledge score must be between 0 and 1")
        self._min_score = float(min_score) if min_score is not None else None
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
        document_ids: Sequence[str] | None = None,
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
            dense_points = client.query_points(
                collection_name=self._spec.physical_collection_name,
                query=vector,
                limit=min(100, max(10, limit * 4)),
                with_payload=True,
                with_vectors=False,
            ).points
        except Exception as exc:
            raise KnowledgeUnavailable("knowledge collection is unavailable") from exc

        dense_by_id = {str(point.id): point for point in dense_points}
        allowed_documents = set(document_ids) if document_ids is not None else None
        if allowed_documents is not None and any(
            not isinstance(value, str) or not value for value in allowed_documents
        ):
            raise ValueError("document_ids are invalid")
        dense_points = [
            point
            for point in dense_points
            if allowed_documents is None
            or isinstance(point.payload, Mapping)
            and point.payload.get("document_id") in allowed_documents
        ]
        dense_by_id = {str(point.id): point for point in dense_points}
        sparse_records = self._sparse_candidates(
            query.strip(), document_version, allowed_documents
        )
        dense_rank = _rank_scores(
            {str(point.id): float(point.score) for point in dense_points}
        )
        sparse_rank = _rank_scores(
            {point_id: float(overlap) for point_id, _, overlap in sparse_records}
        )
        candidate_ids = set(dense_rank) | set(sparse_rank)
        fused = {
            point_id: (1 / (60 + dense_rank[point_id]) if point_id in dense_rank else 0)
            + (1 / (60 + sparse_rank[point_id]) if point_id in sparse_rank else 0)
            for point_id in candidate_ids
        }
        ordered_ids = sorted(
            candidate_ids,
            key=lambda point_id: (-fused[point_id], point_id),
        )
        sparse_payloads = {point_id: payload for point_id, payload, _ in sparse_records}
        payloads = {
            point_id: (
                dense_by_id[point_id].payload
                if point_id in dense_by_id
                else sparse_payloads[point_id]
            )
            for point_id in candidate_ids
        }
        ordered_ids.sort(
            key=lambda point_id: (
                -fused[point_id],
                str((payloads[point_id] or {}).get("document_id", "")),
                str((payloads[point_id] or {}).get("chunk_id", "")),
            )
        )
        chunks: list[KnowledgeChunk] = []
        for point_id in ordered_ids:
            dense_point = dense_by_id.get(point_id)
            dense_score = float(dense_point.score) if dense_point is not None else 0.0
            if (
                self._min_score is not None
                and dense_score < self._min_score
                and point_id not in sparse_rank
            ):
                continue
            payload = (
                dense_point.payload
                if dense_point is not None
                else sparse_payloads[point_id]
            )
            try:
                # score 表达绝对相关性（dense cosine 原始分，0-1），
                # RRF 融合分只决定库内排序——跨库（主库 vs 个人库）合并
                # 比较时语义才一致；库内排名归一值会让小文档库恒得满分。
                score = min(1.0, max(0.0, dense_score))
                chunk = self._chunk_from_payload(payload, score)
            except (TypeError, ValueError):
                continue
            if document_version is None or chunk.version == document_version:
                chunks.append(chunk)
            if len(chunks) == limit:
                break
        return tuple(chunks)

    def _sparse_candidates(
        self,
        query: str,
        document_version: str | None,
        document_ids: set[str] | None = None,
    ) -> list[tuple[str, Mapping[str, object], int]]:
        query_terms = _lexical_terms(query)
        if not query_terms:
            return []
        ranked: list[tuple[int, str, Mapping[str, object]]] = []
        offset = None
        while True:
            records, offset = self._get_client().scroll(
                collection_name=self._spec.physical_collection_name,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for record in records:
                payload = record.payload
                if not isinstance(payload, Mapping):
                    continue
                if (
                    document_version is not None
                    and payload.get("version") != document_version
                ):
                    continue
                if (
                    document_ids is not None
                    and payload.get("document_id") not in document_ids
                ):
                    continue
                haystack = f"{payload.get('title', '')} {payload.get('content', '')}"
                terms = _lexical_terms(haystack)
                overlap = sum(terms.count(term) for term in query_terms)
                if overlap:
                    ranked.append((overlap, str(record.id), payload))
            if offset is None:
                break
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [
            (point_id, payload, overlap) for overlap, point_id, payload in ranked[:100]
        ]

    def list_document_ids(self) -> set[str]:
        """collection 内全部 document_id（H14 对账用；一次全量 scroll）。"""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        collection_filter = Filter(
            must=[
                FieldCondition(
                    key="collection_id",
                    match=MatchValue(value=self._spec.collection_id),
                )
            ]
        )
        document_ids: set[str] = set()
        offset = None
        while True:
            records, offset = self._get_client().scroll(
                collection_name=self._spec.physical_collection_name,
                scroll_filter=collection_filter,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for record in records:
                if isinstance(record.payload, Mapping):
                    document_id = record.payload.get("document_id")
                    if document_id:
                        document_ids.add(str(document_id))
            if offset is None:
                return document_ids

    def list_documents_summary(self) -> dict[str, tuple[str, int]]:
        """document_id -> (title, chunk 数)（I3 对账修复用；一次全量 scroll）。"""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        collection_filter = Filter(
            must=[
                FieldCondition(
                    key="collection_id",
                    match=MatchValue(value=self._spec.collection_id),
                )
            ]
        )
        summary: dict[str, tuple[str, int]] = {}
        offset = None
        while True:
            records, offset = self._get_client().scroll(
                collection_name=self._spec.physical_collection_name,
                scroll_filter=collection_filter,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for record in records:
                payload = record.payload
                if not isinstance(payload, Mapping):
                    continue
                document_id = str(payload.get("document_id") or "")
                if not document_id:
                    continue
                title, count = summary.get(document_id, ("", 0))
                summary[document_id] = (
                    title or str(payload.get("title") or document_id),
                    count + 1,
                )
            if offset is None:
                return summary

    def delete_documents(self, document_ids: Sequence[str]) -> None:
        """Remove all chunks for the supplied document identities."""
        ids = tuple(dict.fromkeys(document_ids))
        if not ids:
            return
        from qdrant_client.models import FieldCondition, Filter, MatchAny

        selector = Filter(
            must=[
                FieldCondition(
                    key="collection_id",
                    match=MatchAny(any=[self._spec.collection_id]),
                ),
                FieldCondition(key="document_id", match=MatchAny(any=list(ids))),
            ]
        )
        self._get_client().delete(
            collection_name=self._spec.physical_collection_name,
            points_selector=selector,
            wait=True,
        )

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


def _lexical_terms(value: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", value.casefold())


def _rank_scores(scores: Mapping[str, float]) -> dict[str, int]:
    """Assign equal rank to equal scores so backend ordering cannot leak in."""
    result: dict[str, int] = {}
    previous: float | None = None
    rank = 0
    for position, (identity, score) in enumerate(
        sorted(scores.items(), key=lambda item: (-item[1], item[0])), start=1
    ):
        if previous is None or not math.isclose(
            score, previous, rel_tol=1e-12, abs_tol=1e-12
        ):
            rank = position
            previous = score
        result[identity] = rank
    return result
