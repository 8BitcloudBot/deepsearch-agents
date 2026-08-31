"""个人知识库入库服务（T2）：入库/覆盖/删除/检索映射与隔离。"""

from pathlib import Path

import pytest

from app.conversation.uploads import UploadKnowledgeStore
from app.knowledge.contracts import EmbeddingDescriptor


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


def make_store(tmp_path: Path) -> UploadKnowledgeStore:
    return UploadKnowledgeStore(
        tmp_path / "user-uploads", FakeEmbedder(), min_score=0.40
    )


class SemanticEmbedder:
    """按字符 bigram 投影的确定性语义 embedder：共享 bigram 越多分数越高。

    FakeEmbedder 的哈希向量没有语义（任意文本两两近似正交且分数随机），
    无法用于"相关>无关"类断言；本夹具注入可判序的语义。
    """

    descriptor = EmbeddingDescriptor(
        provider="fake",
        model="semantic-bigram-fixture",
        version="1.0.0",
        dimension=256,
    )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    @staticmethod
    def _vector(text: str) -> list[float]:
        import hashlib
        import math

        values = [0.0] * 256
        folded = text.casefold()
        for index in range(len(folded) - 1):
            bigram = folded[index : index + 2]
            digest = int(hashlib.md5(bigram.encode("utf-8")).hexdigest()[:8], 16)
            values[digest % 256] += 1.0
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]


def make_semantic_store(tmp_path: Path) -> UploadKnowledgeStore:
    return UploadKnowledgeStore(
        tmp_path / "user-uploads", SemanticEmbedder(), min_score=0.40
    )


def test_ingest_creates_meta_and_same_name_overwrites(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    entry = store.ingest("user-1", "notes.md", "# 标题\n\nLangGraph 是状态机框架。")
    assert entry["name"] == "notes.md"
    assert int(entry["chunks"]) >= 1

    docs = store.list_documents("user-1")
    assert len(docs) == 1 and docs[0]["document_id"] == entry["document_id"]

    # 同名重传 = 覆盖更新，仍只有一条清单
    store.ingest("user-1", "notes.md", "全新内容。")
    assert len(store.list_documents("user-1")) == 1

    # 不同用户彼此不可见（个人知识库物理分库）
    assert store.list_documents("user-2") == ()


def test_remove_drops_document_and_meta(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    entry = store.ingest("user-1", "a.md", "内容段落。")

    assert store.remove("user-1", entry["document_id"]) is True
    assert store.list_documents("user-1") == ()
    assert store.remove("user-1", entry["document_id"]) is False


def test_retriever_for_returns_none_without_documents(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    assert store.retriever_for("user-9") is None

    store.ingest("user-9", "doc.md", "Qdrant 支持本地模式。")
    retriever = store.retriever_for("user-9")
    assert retriever is not None
    items = retriever.search_sync("本地模式")
    assert items and items[0].source_kind == "knowledge"
    assert "本地模式" in items[0].quote or "Qdrant" in items[0].quote


def test_invalid_user_id_is_rejected(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(ValueError):
        store.ingest("../escape", "x.md", "内容")


def test_empty_content_rejected(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(ValueError):
        store.ingest("user-1", "empty.md", "   \n  ")


def test_delete_user_removes_collection_directory_and_caches(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    store.ingest("user-1", "handbook.md", "48小时报销制与住宿标准。")
    assert store.retriever_for("user-1") is not None
    assert (tmp_path / "user-uploads" / "user-1").exists()

    assert store.delete_user("user-1") is True
    assert not (tmp_path / "user-uploads" / "user-1").exists()
    assert store.list_documents("user-1") == ()
    assert store.retriever_for("user-1") is None
    # 缓存清除后重新入库可用（同一生命周期内回收干净）
    store.ingest("user-1", "handbook.md", "重新入库的内容。")
    assert store.retriever_for("user-1") is not None


def test_delete_user_without_directory_reports_false(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    assert store.delete_user("never-uploaded") is False


def test_concurrent_ingest_same_user_is_serialized(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    store = make_store(tmp_path)
    documents = [f"doc-{index}.md" for index in range(4)]

    def ingest(name: str) -> dict[str, str]:
        return store.ingest("user-1", name, f"{name} 的正文内容。")

    with ThreadPoolExecutor(max_workers=4) as pool:
        entries = list(pool.map(ingest, documents))

    assert sorted(entry["name"] for entry in entries) == sorted(documents)
    assert len(store.list_documents("user-1")) == 4
    assert store.retriever_for("user-1") is not None


def test_per_user_document_cap_rejects_new_but_allows_overwrite(tmp_path: Path) -> None:
    store = UploadKnowledgeStore(
        tmp_path / "user-uploads", FakeEmbedder(), min_score=0.40, max_documents=2
    )
    store.ingest("user-1", "a.md", "文档 A 内容。")
    store.ingest("user-1", "b.md", "文档 B 内容。")
    with pytest.raises(ValueError, match="上限"):
        store.ingest("user-1", "c.md", "文档 C 内容。")
    # 同名覆盖不占新名额
    store.ingest("user-1", "a.md", "文档 A 更新内容。")
    assert len(store.list_documents("user-1")) == 2


def test_audit_detects_meta_and_index_drift(tmp_path: Path) -> None:
    import json

    store = make_store(tmp_path)
    store.ingest("user-1", "a.md", "文档 A。")
    entry = store.ingest("user-1", "b.md", "文档 B。")
    assert store.audit("user-1") == {"meta_only": [], "index_only": []}

    # 模拟删除未达：meta 有记录、索引无点
    store._index_for("user-1").delete_documents((entry["document_id"],))
    report = store.audit("user-1")
    assert report["meta_only"] == [entry["document_id"]]

    # 模拟 meta 丢失：索引有数据、meta 无记录（孤儿；b 已在删除未达场景移除）
    meta_path = tmp_path / "user-uploads" / "user-1" / "uploads-meta.json"
    meta_path.write_text(json.dumps([]), encoding="utf-8")
    store._metas.pop("user-1")
    report = store.audit("user-1")
    import hashlib

    expected = [
        "upload-" + hashlib.sha256("a.md".casefold().encode("utf-8")).hexdigest()[:16]
    ]
    assert report["index_only"] == expected


def test_repairs_both_directions_of_meta_index_drift(tmp_path: Path) -> None:
    import json

    store = make_store(tmp_path)
    store.ingest("user-1", "a.md", "文档 A 正文内容。")
    entry_b = store.ingest("user-1", "b.md", "文档 B 正文内容。")

    # index_only：meta 丢失 → 从索引 payload 恢复
    meta_path = tmp_path / "user-uploads" / "user-1" / "uploads-meta.json"
    meta_path.write_text(json.dumps([]), encoding="utf-8")
    store._metas.pop("user-1")
    report = store.repair("user-1")
    assert len(report["restored"]) == 2
    assert store.audit("user-1") == {"meta_only": [], "index_only": []}
    names = {item["name"] for item in store.list_documents("user-1")}
    assert names == {"a.md", "b.md"}

    # meta_only：索引点已丢 → 清死条目
    store._index_for("user-1").delete_documents((entry_b["document_id"],))
    report = store.repair("user-1")
    assert report["dropped"] == [entry_b["document_id"]]
    assert store.audit("user-1") == {"meta_only": [], "index_only": []}
    assert len(store.list_documents("user-1")) == 1


def test_irrelevant_query_must_not_score_perfect(tmp_path: Path) -> None:
    """敌意测试（A1）：个人库小文档集中，语义无关的查询不得因库内
    排名归一而得到高分——score 必须表达绝对相关性，否则用户上传的
    任何文档都会以满分压制主库真实相关证据。

    旧实现（RRF 融合分库内归一）会让两路 rank=1 的 chunk 恒得 1.0/0.5，
    本测试在该实现下必然变红。
    """
    store = make_semantic_store(tmp_path)
    store.ingest(
        "audit-user",
        "travel.md",
        "去年夏天我在大理洱海边骑行了一周，环海西路风景特别好，适合慢节奏的自行车旅行。",
    )
    retriever = store.retriever_for("audit-user")

    related = retriever.search_sync("环海西路骑行的风景怎么样")
    unrelated = retriever.search_sync("量子计算机的纠错码原理是什么")

    assert related, "相关查询应命中"
    # 无关查询含"的"字 lexical 重叠（会进入 sparse_rank 绕过 min_score 的
    # dense 过滤——真机审计中正是此路径让它以满分进池），因此不得依赖过滤，
    # 必须靠分数语义本身区分；要么被过滤为空，要么分数远低于相关查询
    assert not unrelated or unrelated[0].score < related[0].score * 0.5, (
        f"无关查询得分 {unrelated[0].score if unrelated else '无':.3} "
        f"不应接近相关查询 {related[0].score:.3f}"
    )
