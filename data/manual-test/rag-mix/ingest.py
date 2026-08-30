#!/usr/bin/env python3
"""RAG 混合分库测试床：把四主题文档按"全局/个人"分库真实入库。

全局库 = 主语料 Qdrant 索引（.data/knowledge-index-beginner-v2），
        以 ragmix- 前缀 document_id 追加；默认先清理旧注入（幂等）。
个人库 = UploadKnowledgeStore（.data/user-uploads/{user_id}）。

用法：
    uv run --extra dev python data/manual-test/rag-mix/ingest.py
需 .env 提供 KNOWLEDGE_* 等（无 MODEL_API_KEY 也可入库）。
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DOCS_DIR = Path(__file__).resolve().parent / "docs"
GLOBAL_DIR = DOCS_DIR / "global"
PERSONAL_DIR = DOCS_DIR / "personal"
GLOBAL_DOC_PREFIX = "ragmix-"


def _load_env() -> None:
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def _embedder_and_spec():
    from app.conversation.settings import ConversationSettings
    from app.knowledge.contracts import (
        KnowledgeIndexSpec,
        resolve_knowledge_index_path,
    )
    from app.knowledge.embeddings import FastEmbedEmbeddingAdapter

    settings = ConversationSettings.from_env(os.environ)
    embedder = FastEmbedEmbeddingAdapter(
        model=settings.knowledge.embedding_model,
        version=settings.knowledge.embedding_version,
        dimension=settings.knowledge.embedding_dimension,
        cache_dir=str(ROOT / ".cache" / "fastembed"),
    )
    spec = KnowledgeIndexSpec(
        collection_id=settings.knowledge.collection,
        embedding=embedder.descriptor,
        distance="cosine",
        chunking_version="semantic-markdown-v1",
    )
    index_path = resolve_knowledge_index_path(
        settings.knowledge.index_path, runtime_root=ROOT
    )
    return index_path, spec, embedder, settings


def _section_chunks(content: str):
    from app.knowledge.contracts import KnowledgeDocumentChunk

    parts = [
        part.strip()
        for part in re.split(r"\n\s*\n|(?=^#{1,6} )", content, flags=re.MULTILINE)
        if part.strip()
    ]
    chunks = []
    for index, part in enumerate(parts, 1):
        digest = hashlib.sha256(part.encode("utf-8")).hexdigest()[:16]
        chunks.append(
            KnowledgeDocumentChunk(
                chunk_id=f"section-{index:04d}-{digest}",
                content=part[:8000],
                section_path=f"section-{index}",
            )
        )
    return chunks


def ingest_global() -> None:
    from app.knowledge.contracts import KnowledgeDocument
    from app.knowledge.qdrant_local import QdrantLocalKnowledgeIndex

    index_path, spec, embedder, _ = _embedder_and_spec()
    index = QdrantLocalKnowledgeIndex(index_path, spec, embedder, min_score=0.0)

    known_ids = [
        f"{GLOBAL_DOC_PREFIX}{p.stem}" for p in sorted(GLOBAL_DIR.glob("*.md"))
    ]
    index.delete_documents(known_ids)  # 幂等：清理旧注入后重灌

    documents = []
    for path in sorted(GLOBAL_DIR.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        documents.append(
            KnowledgeDocument(
                collection_id=spec.collection_id,
                document_id=f"{GLOBAL_DOC_PREFIX}{path.stem}",
                title=path.stem,
                version="1.0.0",
                chunks=tuple(_section_chunks(content)),
            )
        )
    report = index.index_documents(tuple(documents))
    print(
        f"[global] collection={spec.collection_id} "
        f"indexed={report.indexed_chunks} skipped={report.skipped_chunks}"
    )


def ingest_personal(user_id: str) -> None:
    from app.conversation.settings import ConversationSettings
    from app.conversation.uploads import UploadKnowledgeStore
    from app.knowledge.embeddings import FastEmbedEmbeddingAdapter

    settings = ConversationSettings.from_env(os.environ)
    embedder = FastEmbedEmbeddingAdapter(
        model=settings.knowledge.embedding_model,
        version=settings.knowledge.embedding_version,
        dimension=settings.knowledge.embedding_dimension,
        cache_dir=str(ROOT / ".cache" / "fastembed"),
    )
    store = UploadKnowledgeStore(
        ROOT / ".data" / "user-uploads",
        embedder,
        min_score=settings.knowledge.min_score,
    )
    for path in sorted(PERSONAL_DIR.glob("*.md")):
        entry = store.ingest_path(user_id, path.name, path)
        print(f"[personal:{user_id[:12]}] {entry['name']} chunks={entry['chunks']}")
    print(f"[personal] total documents: {len(store.list_documents(user_id))}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--user-id",
        default="regression-ragmix",
        help="个人库归属用户 id（默认回归专用 id）",
    )
    args = parser.parse_args()
    _load_env()
    ingest_global()
    ingest_personal(args.user_id)


if __name__ == "__main__":
    main()
