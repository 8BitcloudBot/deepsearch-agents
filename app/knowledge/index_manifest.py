"""Strict parser for explicitly selected local knowledge manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.knowledge.contracts import KnowledgeDocument, KnowledgeDocumentChunk

SCHEMA_VERSION = "1.0.0"
_ROOT_FIELDS = frozenset(
    {"schema_version", "collection_id", "chunking_version", "documents"}
)
_DOCUMENT_FIELDS = frozenset({"document_id", "title", "version", "chunks"})
_CHUNK_FIELDS = frozenset({"chunk_id", "content", "section_path", "source_uri"})


def _exact_mapping(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"knowledge manifest {label} fields are invalid")
    return value


def _non_empty_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"knowledge manifest {label} must be a non-empty list")
    return value


def load_knowledge_manifest(
    path: Path,
) -> tuple[str, str, tuple[KnowledgeDocument, ...]]:
    """Load one UTF-8 manifest without discovering or transforming source files."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("knowledge manifest could not be loaded") from exc

    root = _exact_mapping(raw, _ROOT_FIELDS, "root")
    if root["schema_version"] != SCHEMA_VERSION:
        raise ValueError("knowledge manifest schema_version is unsupported")

    documents_raw = _non_empty_list(root["documents"], "documents")
    collection_id = root["collection_id"]
    chunking_version = root["chunking_version"]
    documents: list[KnowledgeDocument] = []
    document_ids: set[str] = set()

    for document_raw in documents_raw:
        document_data = _exact_mapping(document_raw, _DOCUMENT_FIELDS, "document")
        chunks_raw = _non_empty_list(document_data["chunks"], "chunks")
        chunks: list[KnowledgeDocumentChunk] = []
        for chunk_raw in chunks_raw:
            chunk_data = _exact_mapping(chunk_raw, _CHUNK_FIELDS, "chunk")
            chunks.append(KnowledgeDocumentChunk(**chunk_data))

        document = KnowledgeDocument(
            collection_id=collection_id,
            document_id=document_data["document_id"],
            title=document_data["title"],
            version=document_data["version"],
            chunks=tuple(chunks),
        )
        if document.document_id in document_ids:
            raise ValueError("knowledge manifest document IDs must be unique")
        document_ids.add(document.document_id)
        documents.append(document)

    # Validate the manifest-level value even before an index spec is constructed.
    if not isinstance(chunking_version, str) or not chunking_version.strip():
        raise ValueError("knowledge manifest chunking_version is invalid")
    if len(chunking_version) > 128:
        raise ValueError("knowledge manifest chunking_version is invalid")

    return collection_id, chunking_version.strip(), tuple(documents)
