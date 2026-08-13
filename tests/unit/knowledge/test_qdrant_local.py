from pathlib import Path

import pytest

from app.knowledge.contracts import (
    EmbeddingDescriptor,
    KnowledgeDocument,
    KnowledgeDocumentChunk,
    KnowledgeIndexSpec,
    KnowledgeUnavailable,
    stable_point_id,
)
from app.knowledge.qdrant_local import QdrantLocalKnowledgeIndex


class FakeEmbedder:
    descriptor = EmbeddingDescriptor(
        provider="fake",
        model="fixture-embedding",
        version="1.0.0",
        dimension=8,
        query_prefix="query: ",
        document_prefix="passage: ",
    )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    @staticmethod
    def _vector(text: str) -> list[float]:
        values = [0.0] * 8
        for index, char in enumerate(text.encode("utf-8")):
            values[index % 8] += float(char)
        return values


class AlternateFakeEmbedder(FakeEmbedder):
    descriptor = EmbeddingDescriptor(
        provider="fake",
        model="fixture-embedding-v2",
        version="2.0.0",
        dimension=8,
        query_prefix="query: ",
        document_prefix="passage: ",
    )


class UnavailableQueryEmbedder(FakeEmbedder):
    def embed_query(self, text: str) -> list[float]:
        raise RuntimeError("model cache missing at /Users/private/model")


class InvalidSecondVectorEmbedder(FakeEmbedder):
    def __init__(self) -> None:
        self.calls = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        if len(texts) > 1:
            return [self._vector(texts[0]), [0.0]]
        if self.calls == 1:
            return [self._vector(texts[0])]
        return [[0.0]]


def spec() -> KnowledgeIndexSpec:
    return KnowledgeIndexSpec(
        collection_id="fixture-knowledge",
        embedding=FakeEmbedder.descriptor,
        distance="cosine",
        chunking_version="fixture-v1",
    )


def document(*, content: str = "Qdrant Local fixture content.") -> KnowledgeDocument:
    return KnowledgeDocument(
        collection_id="fixture-knowledge",
        document_id="document-1",
        title="Fixture knowledge document",
        version="1.0.0",
        chunks=(
            KnowledgeDocumentChunk(
                chunk_id="chunk-1",
                content=content,
                section_path="Overview",
                source_uri="https://example.test/fixture",
            ),
        ),
    )


def test_qdrant_local_indexes_idempotently_and_returns_identity(tmp_path: Path) -> None:
    index = QdrantLocalKnowledgeIndex(tmp_path / "index", spec(), FakeEmbedder())

    first = index.index_documents((document(),))
    second = index.index_documents((document(),))
    result = index.search("Qdrant Local fixture", limit=3)

    assert first.indexed_chunks == 1
    assert second.indexed_chunks == 0
    assert second.skipped_chunks == 1
    assert len(result) == 1
    assert result[0].collection_id == "fixture-knowledge"
    assert result[0].document_id == "document-1"
    assert result[0].chunk_id == "chunk-1"
    assert result[0].content == "Qdrant Local fixture content."


def test_qdrant_local_min_score_filters_weak_nearest_neighbors(tmp_path: Path) -> None:
    index = QdrantLocalKnowledgeIndex(
        tmp_path / "index", spec(), FakeEmbedder(), min_score=0.99
    )
    index.index_documents((document(),))

    assert index.search("unrelated football result", limit=3) == ()


@pytest.mark.parametrize("value", [-0.01, 1.01, float("nan"), True])
def test_qdrant_local_rejects_invalid_min_score(tmp_path: Path, value: object) -> None:
    with pytest.raises(ValueError, match="score"):
        QdrantLocalKnowledgeIndex(
            tmp_path / "index", spec(), FakeEmbedder(), min_score=value
        )


def test_reindexing_document_removes_stale_chunks_without_touching_other_documents(
    tmp_path: Path,
) -> None:
    index = QdrantLocalKnowledgeIndex(tmp_path / "index", spec(), FakeEmbedder())
    first_document = KnowledgeDocument(
        collection_id="fixture-knowledge",
        document_id="document-1",
        title="Fixture knowledge document",
        version="1.0.0",
        chunks=(
            KnowledgeDocumentChunk(chunk_id="chunk-1", content="Current content."),
            KnowledgeDocumentChunk(chunk_id="chunk-2", content="Removed content."),
        ),
    )
    other_document = KnowledgeDocument(
        collection_id="fixture-knowledge",
        document_id="document-2",
        title="Other fixture document",
        version="1.0.0",
        chunks=(KnowledgeDocumentChunk(chunk_id="chunk-1", content="Other content."),),
    )
    replacement = KnowledgeDocument(
        collection_id="fixture-knowledge",
        document_id="document-1",
        title="Fixture knowledge document",
        version="1.0.0",
        chunks=(
            KnowledgeDocumentChunk(chunk_id="chunk-1", content="Current content."),
        ),
    )
    index.index_documents((first_document, other_document))

    report = index.index_documents((replacement,))

    stale_id = stable_point_id("fixture-knowledge", "document-1", "chunk-2")
    other_id = stable_point_id("fixture-knowledge", "document-2", "chunk-1")
    remaining = index._get_client().retrieve(
        collection_name=spec().physical_collection_name,
        ids=[stale_id, other_id],
        with_payload=True,
        with_vectors=False,
    )
    assert report.indexed_chunks == 0
    assert report.skipped_chunks == 1
    assert [point.id for point in remaining] == [other_id]
    assert "chunk-2" not in {
        chunk.chunk_id for chunk in index.search("Removed content", limit=10)
    }


def test_invalid_vector_batch_does_not_partially_write_points(tmp_path: Path) -> None:
    index = QdrantLocalKnowledgeIndex(
        tmp_path / "index", spec(), InvalidSecondVectorEmbedder()
    )
    two_chunks = KnowledgeDocument(
        collection_id="fixture-knowledge",
        document_id="document-1",
        title="Fixture knowledge document",
        version="1.0.0",
        chunks=(
            KnowledgeDocumentChunk(chunk_id="chunk-1", content="First content."),
            KnowledgeDocumentChunk(chunk_id="chunk-2", content="Second content."),
        ),
    )

    with pytest.raises(ValueError, match="dimension"):
        index.index_documents((two_chunks,))

    point_ids = [
        stable_point_id("fixture-knowledge", "document-1", "chunk-1"),
        stable_point_id("fixture-knowledge", "document-1", "chunk-2"),
    ]
    assert (
        index._get_client().retrieve(
            collection_name=spec().physical_collection_name,
            ids=point_ids,
            with_payload=False,
            with_vectors=False,
        )
        == []
    )


def test_qdrant_local_rejects_fingerprint_mismatch(tmp_path: Path) -> None:
    index = QdrantLocalKnowledgeIndex(tmp_path / "index", spec(), FakeEmbedder())
    index.index_documents((document(),))
    changed = KnowledgeIndexSpec(
        collection_id="fixture-knowledge",
        embedding=FakeEmbedder.descriptor,
        distance="dot",
        chunking_version="fixture-v1",
    )

    with pytest.raises(ValueError, match="fingerprint"):
        QdrantLocalKnowledgeIndex(tmp_path / "index", changed, FakeEmbedder())


@pytest.mark.parametrize(
    ("changed", "embedder"),
    [
        (
            KnowledgeIndexSpec(
                collection_id="fixture-knowledge",
                embedding=AlternateFakeEmbedder.descriptor,
                distance="cosine",
                chunking_version="fixture-v1",
            ),
            AlternateFakeEmbedder(),
        ),
        (
            KnowledgeIndexSpec(
                collection_id="fixture-knowledge",
                embedding=FakeEmbedder.descriptor,
                distance="cosine",
                chunking_version="fixture-v2",
            ),
            FakeEmbedder(),
        ),
    ],
)
def test_qdrant_local_rejects_embedding_or_chunking_fingerprint_mismatch(
    tmp_path: Path,
    changed: KnowledgeIndexSpec,
    embedder: FakeEmbedder,
) -> None:
    index = QdrantLocalKnowledgeIndex(tmp_path / "index", spec(), FakeEmbedder())
    index.index_documents((document(),))

    with pytest.raises(ValueError, match="fingerprint"):
        QdrantLocalKnowledgeIndex(tmp_path / "index", changed, embedder)


def test_search_skips_payload_with_wrong_embedding_fingerprint(
    tmp_path: Path,
) -> None:
    index = QdrantLocalKnowledgeIndex(tmp_path / "index", spec(), FakeEmbedder())
    index.index_documents((document(),))
    index._get_client().set_payload(
        collection_name=spec().physical_collection_name,
        payload={"embedding_fingerprint": "0" * 64},
        points=[stable_point_id("fixture-knowledge", "document-1", "chunk-1")],
        wait=True,
    )

    assert index.search("Qdrant Local fixture") == ()


def test_qdrant_local_rejects_unknown_collection_and_missing_index(
    tmp_path: Path,
) -> None:
    index = QdrantLocalKnowledgeIndex(tmp_path / "index", spec(), FakeEmbedder())

    with pytest.raises(KnowledgeUnavailable, match="not indexed"):
        index.search("anything")

    with pytest.raises(ValueError, match="collection_id"):
        index.index_documents(
            (
                KnowledgeDocument(
                    collection_id="other-collection",
                    document_id="document-1",
                    title="Fixture",
                    version="1.0.0",
                    chunks=(
                        KnowledgeDocumentChunk(chunk_id="chunk-1", content="text"),
                    ),
                ),
            )
        )


def test_search_maps_embedding_failure_to_structured_unavailable(
    tmp_path: Path,
) -> None:
    index = QdrantLocalKnowledgeIndex(
        tmp_path / "index", spec(), UnavailableQueryEmbedder()
    )
    index.index_documents((document(),))

    with pytest.raises(KnowledgeUnavailable) as caught:
        index.search("anything")

    assert str(caught.value) == "knowledge embedding model is unavailable"
    assert "/Users/" not in str(caught.value)


def test_search_maps_collection_open_failure_to_structured_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "index"
    path.mkdir()
    index = QdrantLocalKnowledgeIndex(path, spec(), FakeEmbedder())

    def fail_collection_check() -> bool:
        raise RuntimeError("corrupt storage at /Users/private/index")

    monkeypatch.setattr(index, "_collection_exists", fail_collection_check)

    with pytest.raises(KnowledgeUnavailable) as caught:
        index.search("anything")

    assert str(caught.value) == "knowledge collection is unavailable"
    assert "/Users/" not in str(caught.value)


def test_search_order_is_stable_for_equal_scores(tmp_path: Path) -> None:
    index = QdrantLocalKnowledgeIndex(tmp_path / "index", spec(), FakeEmbedder())
    docs = (
        document(content="same fixture content"),
        KnowledgeDocument(
            collection_id="fixture-knowledge",
            document_id="document-2",
            title="Second fixture",
            version="1.0.0",
            chunks=(
                KnowledgeDocumentChunk(
                    chunk_id="chunk-2", content="same fixture content"
                ),
            ),
        ),
    )
    index.index_documents(docs)

    result = index.search("same fixture", limit=2)

    assert [item.chunk_id for item in result] == ["chunk-1", "chunk-2"]
