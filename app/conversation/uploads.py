"""个人知识库入库服务（RAG 化的文档上传）。

每个用户拥有一个独立的 Qdrant collection（物理目录按 user_id 分离），
与冻结语料主库完全隔离：index_knowledge.py 重建主库永不触碰用户库。
入库走 parse → section 切块 → embed → 增量 upsert；同名重传即覆盖更新，
删除经 delete_documents 回滚。检索由 runtime.UserKnowledgeRetriever 承担，
结果并入引擎 knowledge 分支统一评分排序。
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

from app.knowledge.contracts import KnowledgeDocument, KnowledgeDocumentChunk

CHUNKING_VERSION = "heading-section-v1"
_META_NAME = "uploads-meta.json"
_SAFE_USER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def _section_chunks(content: str) -> tuple[KnowledgeDocumentChunk, ...]:
    """按 Markdown 标题与空行切段，chunk_id 用内容哈希保持稳定。"""
    parts = [
        part.strip()
        for part in re.split(r"\n\s*\n|(?=^#{1,6} )", content, flags=re.MULTILINE)
        if part.strip()
    ]
    values: list[KnowledgeDocumentChunk] = []
    for index, part in enumerate(parts, 1):
        digest = hashlib.sha256(part.encode("utf-8")).hexdigest()[:16]
        values.append(
            KnowledgeDocumentChunk(
                chunk_id=f"section-{index:04d}-{digest}",
                content=part[:8000],
                section_path=f"section-{index}",
            )
        )
    return tuple(values)


class UploadKnowledgeStore:
    """per-user Qdrant collection 的入库/删除/清单管理器。

    embedder 由调用方注入（与主库共享同一 FastEmbed 实例）；
    min_score 语义与主库 KnowledgeEvidenceRetriever 一致。
    """

    def __init__(self, root: Path, embedder: Any, min_score: float):
        self._root = Path(root)
        self._embedder = embedder
        self._min_score = min_score
        self._indexes: dict[str, Any] = {}
        self._metas: dict[str, list[dict[str, str]]] = {}

    # -- 内部 -----------------------------------------------------------

    def _user_dir(self, user_id: str) -> Path:
        if not _SAFE_USER_RE.fullmatch(str(user_id)):
            raise ValueError("upload store user id is invalid")
        return self._root / user_id

    def _index_for(self, user_id: str) -> Any:
        cached = self._indexes.get(user_id)
        if cached is not None:
            return cached
        from app.knowledge.contracts import KnowledgeIndexSpec
        from app.knowledge.qdrant_local import QdrantLocalKnowledgeIndex

        spec = KnowledgeIndexSpec(
            collection_id=f"uploads-{user_id}",
            embedding=self._embedder.descriptor,
            distance="cosine",
            chunking_version=CHUNKING_VERSION,
        )
        index = QdrantLocalKnowledgeIndex(
            self._user_dir(user_id), spec, self._embedder, min_score=self._min_score
        )
        self._indexes[user_id] = index
        return index

    def _meta_path(self, user_id: str) -> Path:
        return self._user_dir(user_id) / _META_NAME

    def _meta(self, user_id: str) -> list[dict[str, str]]:
        if user_id not in self._metas:
            path = self._meta_path(user_id)
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                self._metas[user_id] = raw if isinstance(raw, list) else []
            except (OSError, json.JSONDecodeError):
                self._metas[user_id] = []
        return self._metas[user_id]

    def _save_meta(self, user_id: str) -> None:
        directory = self._user_dir(user_id)
        directory.mkdir(parents=True, exist_ok=True)
        self._meta_path(user_id).write_text(
            json.dumps(self._meta(user_id), ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    @staticmethod
    def _document_id(name: str) -> str:
        # 同名文件重复入库=覆盖更新：doc id 由文件名派生且必为安全标识符
        digest = hashlib.sha256(name.casefold().encode("utf-8")).hexdigest()[:16]
        return f"upload-{digest}"

    # -- 公开接口 --------------------------------------------------------

    def ingest_path(self, user_id: str, name: str, path: Path) -> dict[str, str]:
        content = read_supported_file(path)
        return self.ingest(user_id, name, content)

    def ingest(self, user_id: str, name: str, content: str) -> dict[str, str]:
        if not name.strip() or not content.strip():
            raise ValueError("上传的文档内容为空")
        document_id = self._document_id(name)
        document = KnowledgeDocument(
            collection_id=f"uploads-{user_id}",
            document_id=document_id,
            title=name[:200],
            version="1.0.0",
            chunks=_section_chunks(content),
        )
        if not document.chunks:
            raise ValueError("文档未能切分出任何内容块")
        index = self._index_for(user_id)
        index.index_documents((document,))

        entry = {
            "document_id": document_id,
            "name": name[:200],
            "chunks": str(len(document.chunks)),
        }
        meta = [
            item
            for item in self._meta(user_id)
            if item.get("document_id") != document_id
        ]
        meta.insert(0, entry)
        self._metas[user_id] = meta
        self._save_meta(user_id)
        return entry

    def remove(self, user_id: str, document_id: str) -> bool:
        before = self._meta(user_id)
        after = [item for item in before if item.get("document_id") != document_id]
        if len(after) == len(before):
            return False
        self._index_for(user_id).delete_documents((document_id,))
        self._metas[user_id] = after
        self._save_meta(user_id)
        return True

    def delete_user(self, user_id: str) -> bool:
        """管理员清理用户数据时连带删除其整个个人知识库（G3 数据完整性）。

        清除内存缓存后整目录移除；目录不存在视为已清理，返回 False。
        """
        directory = self._user_dir(user_id)
        self._indexes.pop(user_id, None)
        self._metas.pop(user_id, None)
        if not directory.exists():
            return False
        shutil.rmtree(directory)
        return True

    def list_documents(self, user_id: str) -> tuple[dict[str, str], ...]:
        return tuple(dict(item) for item in self._meta(user_id))

    def retriever_for(self, user_id: str) -> Any:
        """当前用户的个人知识库检索器；库不存在或未入库时返回 None。"""
        if not self._meta(user_id):
            return None
        from app.conversation.runtime import UserKnowledgeRetriever

        return UserKnowledgeRetriever(self._index_for(user_id))


def read_supported_file(path: Path) -> str:
    """把上传文件提取为纯文本（pdf/docx/xlsx/md/txt），越界即拒绝。"""
    from app.knowledge.readers import (
        ALLOWED_EXTENSIONS,
        MAX_FILE_SIZE_BYTES,
        read_docx_file,
        read_pdf_file,
        read_text_file,
        read_xlsx_file,
        validate_upload_file,
    )

    extension = path.suffix.casefold()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("不支持的文档类型")
    if path.stat().st_size > MAX_FILE_SIZE_BYTES:
        raise ValueError("文档过大")
    validate_upload_file(path)
    readers = {
        ".txt": read_text_file,
        ".md": read_text_file,
        ".pdf": read_pdf_file,
        ".docx": read_docx_file,
        ".xlsx": read_xlsx_file,
    }
    return readers[extension](path)
