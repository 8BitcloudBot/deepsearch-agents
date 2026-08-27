from pathlib import Path
from uuid import UUID

import pytest

from app.knowledge.contracts import (
    EmbeddingDescriptor,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentChunk,
    KnowledgeIndexSpec,
    KnowledgeUnavailable,
    resolve_knowledge_index_path,
    stable_point_id,
)


def embedding() -> EmbeddingDescriptor:
    return EmbeddingDescriptor(
        provider="fake",
        model="fixture-embedding",
        version="1.0.0",
        dimension=8,
        query_prefix="query: ",
        document_prefix="passage: ",
    )


def test_index_spec_fingerprint_changes_with_embedding_or_chunking() -> None:
    base = KnowledgeIndexSpec(
        collection_id="deepsearch-showcase-v1",
        embedding=embedding(),
        distance="cosine",
        chunking_version="fixture-v1",
    )
    different_model = KnowledgeIndexSpec(
        collection_id=base.collection_id,
        embedding=EmbeddingDescriptor(
            provider="fake",
            model="fixture-embedding-v2",
            version="1.0.0",
            dimension=8,
            query_prefix="query: ",
            document_prefix="passage: ",
        ),
        distance=base.distance,
        chunking_version=base.chunking_version,
    )
    different_chunking = KnowledgeIndexSpec(
        collection_id=base.collection_id,
        embedding=base.embedding,
        distance=base.distance,
        chunking_version="fixture-v2",
    )

    assert base.embedding_fingerprint != different_model.embedding_fingerprint
    assert base.index_fingerprint != different_model.index_fingerprint
    assert base.index_fingerprint != different_chunking.index_fingerprint
    assert base.physical_collection_name.startswith("deepsearch-showcase-v1-")


def test_stable_point_id_is_deterministic_uuid() -> None:
    first = stable_point_id("collection-a", "document-a", "chunk-a")
    second = stable_point_id("collection-a", "document-a", "chunk-a")

    assert first == second
    assert str(UUID(first)) == first
    assert first != stable_point_id("collection-a", "document-a", "chunk-b")


@pytest.mark.parametrize(
    "configured",
    ["/tmp/private-index", "../private-index", "nested/../../private-index", "~/index"],
)
def test_index_path_rejects_absolute_and_traversal(
    tmp_path: Path, configured: str
) -> None:
    with pytest.raises(ValueError, match="knowledge index path"):
        resolve_knowledge_index_path(configured, runtime_root=tmp_path)


def test_index_path_resolves_inside_runtime_root(tmp_path: Path) -> None:
    result = resolve_knowledge_index_path(
        ".data/knowledge-index", runtime_root=tmp_path
    )

    assert result == (tmp_path / ".data/knowledge-index").resolve()


@pytest.mark.parametrize(
    "document",
    [
        KnowledgeDocument(
            collection_id="collection-a",
            document_id="document-a",
            title="Fixture document",
            version="1.0.0",
            chunks=(
                KnowledgeDocumentChunk(
                    chunk_id="chunk-a",
                    content="Safe fixture content.",
                    source_uri="https://example.test/fixture",
                ),
            ),
        ),
    ],
)
def test_document_contract_accepts_safe_fixture(document: KnowledgeDocument) -> None:
    assert document.chunks[0].content == "Safe fixture content."


@pytest.mark.parametrize(
    "kwargs",
    [
        {"collection_id": "../private"},
        {"document_id": "/Users/private/document"},
        {"chunk_id": "../../chunk"},
        {"source_uri": "file:///Users/private/document.md"},
    ],
)
def test_document_contract_rejects_unsafe_metadata(kwargs: dict[str, str]) -> None:
    document_values = {
        "collection_id": kwargs.get("collection_id", "collection-a"),
        "document_id": kwargs.get("document_id", "document-a"),
        "title": "Fixture document",
        "version": "1.0.0",
    }
    chunk_values = {
        "chunk_id": kwargs.get("chunk_id", "chunk-a"),
        "content": "Safe fixture content.",
        "source_uri": kwargs.get("source_uri"),
    }

    with pytest.raises(ValueError):
        KnowledgeDocument(
            **document_values,
            chunks=(KnowledgeDocumentChunk(**chunk_values),),
        )


def test_knowledge_chunk_rejects_non_finite_score() -> None:
    with pytest.raises(ValueError, match="score"):
        KnowledgeChunk(
            collection_id="collection-a",
            document_id="document-a",
            chunk_id="chunk-a",
            title="Fixture document",
            content="Safe fixture content.",
            score=float("nan"),
            version="1.0.0",
        )


def test_knowledge_unavailable_is_structured_and_path_safe() -> None:
    error = KnowledgeUnavailable("collection is not indexed")

    assert error.code == "knowledge-unavailable"
    assert error.as_limitation() == {
        "code": "knowledge-unavailable",
        "message": "collection is not indexed",
    }
