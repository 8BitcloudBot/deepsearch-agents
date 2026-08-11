"""Explicit real FastEmbed + Qdrant Local smoke with non-sensitive fixture data."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.knowledge.contracts import (
    KnowledgeDocument,
    KnowledgeDocumentChunk,
    KnowledgeIndexSpec,
)
from app.knowledge.embeddings import FastEmbedEmbeddingAdapter
from app.knowledge.qdrant_local import QdrantLocalKnowledgeIndex
from app.showcase.delivery import build_live_citation_document
from app.showcase.locator_adapters import normalize_knowledge_chunk
from app.showcase.research import LiveSourceCollector

SMOKE_FLAG = "PHASE45_FASTEMBED_SMOKE"
MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
THREAD_ID = "aaaaaaaa-0000-4000-8000-000000000001"
FIXTURE = (
    Path(__file__).resolve().parents[2] / "fixtures" / "phase4_5" / "knowledge.json"
)


@pytest.mark.integration
def test_real_fastembed_qdrant_local_citation_smoke(tmp_path: Path) -> None:
    if os.environ.get(SMOKE_FLAG) != "1":
        pytest.skip(f"{SMOKE_FLAG} is not set to '1': no model is loaded or downloaded")

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    embedder = FastEmbedEmbeddingAdapter(
        model=MODEL,
        version="0.8.0",
        dimension=384,
        cache_dir=str((Path.cwd() / ".cache" / "fastembed").resolve()),
    )
    spec = KnowledgeIndexSpec(
        collection_id=str(fixture["collection_id"]),
        embedding=embedder.descriptor,
        chunking_version="smoke-v1",
    )
    index = QdrantLocalKnowledgeIndex(tmp_path / "qdrant-local", spec, embedder)
    document = KnowledgeDocument(
        collection_id=str(fixture["collection_id"]),
        document_id=str(fixture["document_id"]),
        title=str(fixture["title"]),
        version=str(fixture["version"]),
        chunks=(
            KnowledgeDocumentChunk(
                chunk_id=str(fixture["chunk_id"]),
                content=str(fixture["content"]),
                section_path=str(fixture["section_path"]),
                source_uri=str(fixture["source_uri"]),
            ),
        ),
    )

    first = index.index_documents((document,))
    second = index.index_documents((document,))
    results = index.search("How does local knowledge retrieval work?", limit=1)

    assert first.indexed_chunks == 1
    assert second.skipped_chunks == 1
    assert len(results) == 1
    chunk = results[0]
    assert (chunk.collection_id, chunk.document_id, chunk.chunk_id) == (
        fixture["collection_id"],
        fixture["document_id"],
        fixture["chunk_id"],
    )

    source = normalize_knowledge_chunk(
        chunk,
        captured_at=str(fixture["captured_at"]),
    )
    collector = LiveSourceCollector(THREAD_ID)
    collector.add(source, quote=chunk.content)
    citation = build_live_citation_document(
        THREAD_ID,
        collector.snapshot("Local knowledge retrieval returned fixture evidence."),
    ).as_dict()

    assert citation["schema_version"] == "2.0.0"
    assert citation["sources"][0]["source_kind"] == "knowledge"
    assert citation["evidence"][0]["locator"] == {
        "kind": "chunk",
        "value": (
            f"{fixture['collection_id']}:{fixture['document_id']}:{fixture['chunk_id']}"
        ),
    }
