#!/usr/bin/env python3
"""RAG 混合分库测试床：四主题文档按"共享业务库/个人"分库真实入库。

共享业务库 = UploadKnowledgeStore 的 shared 用户（.data/user-uploads/shared），
            与冻结语料主库（.data/knowledge-index-beginner-v2）物理隔离
           （ragmix 审计：跨主题干扰修复）；旧版曾注入主库，本脚本负责清理。
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

CORPUS_DIR = Path(__file__).resolve().parent / "corpus"
SHARED_DIR = CORPUS_DIR / "shared"
PERSONAL_DIR = CORPUS_DIR / "personal"
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


def cleanup_main_library() -> None:
    """清理旧版注入主库的 ragmix-* 文档（跨主题干扰修复的迁移步骤）。"""
    from app.knowledge.qdrant_local import QdrantLocalKnowledgeIndex

    index_path, spec, embedder, _ = _embedder_and_spec()
    index = QdrantLocalKnowledgeIndex(index_path, spec, embedder, min_score=0.0)
    known_ids = [
        f"{GLOBAL_DOC_PREFIX}{p.stem}" for p in sorted(CORPUS_DIR.glob("../docs/global/*.md"))
    ]  # 旧版主库注入清理（ragmix-*）
    index.delete_documents(known_ids)
    print(f"[main-library] cleaned {len(known_ids)} legacy ragmix documents (if any)")


def ingest_shared(store, shared_user: str) -> None:
    # 清理该用户下不在新语料清单中的旧文档（同名覆盖 + 异名清除 = 全量同步）
    new_names = {p.name for p in sorted(SHARED_DIR.glob("*.md"))}
    for existing in store.list_documents(shared_user):
        if existing["name"] not in new_names:
            store.remove(shared_user, existing["document_id"])
            print(f"[shared] removed stale: {existing['name']}")
    for path in sorted(SHARED_DIR.glob("*.md")):
        entry = store.ingest_path(shared_user, path.name, path)
        print(f"[shared] {entry['name']} chunks={entry['chunks']}")
    print(f"[shared] total documents: {len(store.list_documents(shared_user))}")


def ingest_personal(store, user_id: str) -> None:
    # 个人库是用户数据：脚本只做同名覆盖入库，**永不删除**任何已有文档
    # （fail-safe；此前 stale 清理会误删用户经 UI 上传的文档）。
    for path in sorted(PERSONAL_DIR.glob("*.md")):
        entry = store.ingest_path(user_id, path.name, path)
        print(f"[personal:{user_id[:12]}] {entry['name']} chunks={entry['chunks']}")
    print(f"[personal] total documents: {len(store.list_documents(user_id))}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--user-id",
        default=None,
        help="个人库归属用户 id；缺省自动使用预置 user 账号的 uuid",
    )
    args = parser.parse_args()
    _load_env()

    from app.conversation.settings import ConversationSettings
    from app.conversation.store import ConversationStore
    from app.conversation.uploads import (
        SHARED_KNOWLEDGE_USER,
        UPLOADS_MIN_SCORE,
        UploadKnowledgeStore,
    )
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
        min_score=UPLOADS_MIN_SCORE,
    )

    cleanup_main_library()
    ingest_shared(store, SHARED_KNOWLEDGE_USER)
    user_id = args.user_id
    if user_id is None:
        boot_store = ConversationStore(ROOT / ".data" / "smoke-ragmix.sqlite3")
        user_id = boot_store.authenticate("user", "0000").id
    ingest_personal(store, user_id)


if __name__ == "__main__":
    main()
