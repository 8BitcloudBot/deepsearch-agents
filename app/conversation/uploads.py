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
import threading
from pathlib import Path
from typing import Any

from app.knowledge.contracts import KnowledgeDocument, KnowledgeDocumentChunk

CHUNKING_VERSION = "heading-section-v1"
# 共享业务知识库的用户标识：与个人库共用同一套 uploads 基础设施，
# 物理上与冻结语料主库、个人库三分隔离（ragmix 审计：跨主题干扰修复）。
SHARED_KNOWLEDGE_USER = "shared"
# uploads 系（shared/个人）召回阈值采用 **fused 口径**（min_score_mode="fused"）：
# dense 绝对分对查询长度敏感（长查询整体崩塌，ragmix 新语料实测零命中），
# fused 库内排名归一对长度稳定。fused 口径下单路 rank1=0.5，0.40 约等于
# 单路 rank≤45 的召回下限（小型业务库 ≤250 chunks 内即"前 1/5"）。
UPLOADS_MIN_SCORE = 0.40
_META_NAME = "uploads-meta.json"
MAX_DOCUMENTS_PER_USER = 50  # 每用户文档数上限（H6；同名覆盖不占新名额）
_SAFE_USER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def _section_chunks(content: str) -> tuple[KnowledgeDocumentChunk, ...]:
    """按 Markdown 标题与空行切段，chunk_id 用内容哈希保持稳定。

    标题行与其紧随的内容合并为同一 chunk：标题被切成孤立 chunk 后
    只有语义没有内容（ragmix 实测"## 自托管要求"下的硬件规格因
    无标题语义被 min_score 过滤，综合器据此答"资料未给出"）。
    """
    raw_parts = [
        part.strip()
        for part in re.split(r"\n\s*\n|(?=^#{1,6} )", content, flags=re.MULTILINE)
        if part.strip()
    ]
    parts: list[str] = []
    for part in raw_parts:
        is_bare_heading = (
            part.startswith("#")
            and "\n" not in part
            and len(part) <= 120
        )
        if is_bare_heading and parts:
            parts[-1] = f"{parts[-1]}\n{part}"
        elif is_bare_heading:
            parts.append(part)
        elif parts and parts[-1].startswith("#") and "\n" not in parts[-1]:
            # 前一 part 是孤立标题（首个 chunk 即标题）：并进来
            parts[-1] = f"{parts[-1]}\n{part}"
        else:
            parts.append(part)
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

    def __init__(
        self,
        root: Path,
        embedder: Any,
        min_score: float,
        *,
        max_documents: int = MAX_DOCUMENTS_PER_USER,
    ):
        self._root = Path(root)
        self._embedder = embedder
        self._min_score = min_score
        self._indexes: dict[str, Any] = {}
        self._metas: dict[str, list[dict[str, str]]] = {}
        # per-user 写锁（G8）：入库转入工作线程后 Qdrant local 不允许并发写，
        # 同一用户的 ingest/remove/delete_user 必须互斥。
        self._user_locks: dict[str, threading.Lock] = {}
        self._max_documents = max_documents

    # -- 内部 -----------------------------------------------------------

    def _user_dir(self, user_id: str) -> Path:
        if not _SAFE_USER_RE.fullmatch(str(user_id)):
            raise ValueError("upload store user id is invalid")
        return self._root / user_id

    def _lock_for(self, user_id: str) -> threading.Lock:
        # dict.setdefault 原子：并发首建时各线程拿到同一把锁
        return self._user_locks.setdefault(user_id, threading.Lock())

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
            self._user_dir(user_id),
            spec,
            self._embedder,
            min_score=self._min_score,
            min_score_mode="fused",
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
        with self._lock_for(user_id):
            meta = [
                item
                for item in self._meta(user_id)
                if item.get("document_id") != document_id
            ]
            if len(meta) >= self._max_documents:
                raise ValueError(
                    f"个人知识库文档数量已达上限（{self._max_documents}），请先删除部分文档"
                )
            index = self._index_for(user_id)
            index.index_documents((document,))

            entry = {
                "document_id": document_id,
                "name": name[:200],
                "chunks": str(len(document.chunks)),
            }
            meta.insert(0, entry)
            self._metas[user_id] = meta
            self._save_meta(user_id)
        return entry

    def remove(self, user_id: str, document_id: str) -> bool:
        with self._lock_for(user_id):
            before = self._meta(user_id)
            after = [
                item for item in before if item.get("document_id") != document_id
            ]
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
        with self._lock_for(user_id):
            self._indexes.pop(user_id, None)
            self._metas.pop(user_id, None)
            if not directory.exists():
                return False
            shutil.rmtree(directory)
            return True

    def list_documents(self, user_id: str) -> tuple[dict[str, str], ...]:
        return tuple(dict(item) for item in self._meta(user_id))

    def audit(self, user_id: str) -> dict[str, list[str]]:
        """meta 与索引对账（H14，只读不修）。

        meta_only：meta 有记录但索引无点（删除未达/索引丢失）；
        index_only：索引有数据但 meta 无记录（meta 损坏或写盘失败的孤儿）。
        任一侧非空即说明该用户库需要人工干预或重建。
        """
        meta_ids = {item["document_id"] for item in self._meta(user_id)}
        index_ids = self._index_for(user_id).list_document_ids()
        return {
            "meta_only": sorted(meta_ids - index_ids),
            "index_only": sorted(index_ids - meta_ids),
        }

    def repair(self, user_id: str) -> dict[str, list[str]]:
        """对账差异的自动修复（I3；与 audit 配对，修复后 audit 归零）。

        index_only（meta 丢失的孤儿数据）：从索引 payload 恢复 meta 条目
        （document_id/title/块数均可恢复）；meta_only（索引点已丢）：
        清除死条目避免误导。均不可恢复时保留人工介入空间。
        """
        with self._lock_for(user_id):
            summary = self._index_for(user_id).list_documents_summary()
            meta = [
                item
                for item in self._meta(user_id)
                if item.get("document_id") in summary
            ]
            dropped = sorted(
                item.get("document_id", "")
                for item in self._meta(user_id)
                if item.get("document_id") not in summary
            )
            known = {item["document_id"] for item in meta}
            restored = sorted(set(summary) - known)
            for document_id in restored:
                title, chunks = summary[document_id]
                meta.insert(
                    0,
                    {
                        "document_id": document_id,
                        "name": title[:200],
                        "chunks": str(chunks),
                    },
                )
            if restored or dropped:
                self._metas[user_id] = meta
                self._save_meta(user_id)
            return {"restored": restored, "dropped": dropped}

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
