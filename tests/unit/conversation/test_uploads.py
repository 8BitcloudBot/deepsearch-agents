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
