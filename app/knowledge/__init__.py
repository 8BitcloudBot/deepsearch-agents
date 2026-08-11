"""Vendor-neutral local knowledge retrieval boundary."""

from app.knowledge.contracts import (
    EmbeddingAdapter,
    EmbeddingDescriptor,
    IndexReport,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentChunk,
    KnowledgeIndexer,
    KnowledgeIndexSpec,
    KnowledgeRetriever,
    KnowledgeUnavailable,
    resolve_knowledge_index_path,
    stable_point_id,
)
from app.knowledge.index_manifest import load_knowledge_manifest

__all__ = [
    "EmbeddingAdapter",
    "EmbeddingDescriptor",
    "IndexReport",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "KnowledgeDocumentChunk",
    "KnowledgeIndexer",
    "KnowledgeIndexSpec",
    "KnowledgeRetriever",
    "KnowledgeUnavailable",
    "load_knowledge_manifest",
    "resolve_knowledge_index_path",
    "stable_point_id",
]
