#!/usr/bin/env python3
"""Validate or explicitly index a local knowledge manifest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.knowledge.contracts import (  # noqa: E402
    EmbeddingDescriptor,
    KnowledgeIndexSpec,
    resolve_knowledge_index_path,
)
from app.knowledge.index_manifest import load_knowledge_manifest  # noqa: E402

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_VERSION = "0.8.0"
EMBEDDING_DIMENSION = 384


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="index_knowledge.py",
        description="Validate or index one explicit local knowledge manifest.",
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--index-path", required=True)
    parser.add_argument("--collection", required=True)
    parser.add_argument("--validate-only", action="store_true")
    return parser


def _print_report(
    *,
    collection: str,
    documents: int,
    chunks: int,
    fingerprint: str,
    indexed: int,
    skipped: int,
) -> None:
    print(
        f"collection={collection} documents={documents} chunks={chunks} "
        f"fingerprint={fingerprint} indexed={indexed} skipped={skipped}"
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        collection, chunking_version, documents = load_knowledge_manifest(args.manifest)
        if args.collection != collection:
            raise ValueError("collection mismatch")
        index_path = resolve_knowledge_index_path(
            args.index_path, runtime_root=Path.cwd()
        )
        descriptor = EmbeddingDescriptor(
            provider="fastembed",
            model=EMBEDDING_MODEL,
            version=EMBEDDING_VERSION,
            dimension=EMBEDDING_DIMENSION,
        )
        spec = KnowledgeIndexSpec(
            collection_id=collection,
            embedding=descriptor,
            distance="cosine",
            chunking_version=chunking_version,
        )
    except Exception:
        print(
            "[index-knowledge] error: manifest or configuration is invalid",
            file=sys.stderr,
        )
        return 2

    chunk_count = sum(len(document.chunks) for document in documents)
    if args.validate_only:
        _print_report(
            collection=collection,
            documents=len(documents),
            chunks=chunk_count,
            fingerprint=spec.index_fingerprint,
            indexed=0,
            skipped=0,
        )
        return 0

    try:
        from app.knowledge.embeddings import FastEmbedEmbeddingAdapter
        from app.knowledge.qdrant_local import QdrantLocalKnowledgeIndex

        embedder = FastEmbedEmbeddingAdapter(
            model=EMBEDDING_MODEL,
            version=EMBEDDING_VERSION,
            dimension=EMBEDDING_DIMENSION,
            cache_dir=str((Path.cwd() / ".cache" / "fastembed").resolve()),
        )
        index = QdrantLocalKnowledgeIndex(index_path, spec, embedder)
        report = index.index_documents(documents)
    except Exception:
        print("[index-knowledge] error: knowledge indexing failed", file=sys.stderr)
        return 1

    _print_report(
        collection=report.collection_id,
        documents=len(documents),
        chunks=chunk_count,
        fingerprint=report.index_fingerprint,
        indexed=report.indexed_chunks,
        skipped=report.skipped_chunks,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
