from pathlib import Path

from app.conversation.file_index import SessionFileIndex
from app.knowledge.embeddings import FakeEmbeddingAdapter


def test_session_file_index_isolated_by_user_and_conversation(tmp_path: Path) -> None:
    first = SessionFileIndex(tmp_path, FakeEmbeddingAdapter(dimension=8))
    second = SessionFileIndex(tmp_path, FakeEmbeddingAdapter(dimension=8))
    first.index_attachment(
        "user-a",
        "conversation-a",
        "file-a",
        "notes.md",
        "LangGraph 状态图管理回合。",
    )

    assert first.search("user-a", "conversation-a", ("file-a",), "状态图")
    assert second.search("user-b", "conversation-b", ("file-a",), "状态图") == ()


def test_session_file_index_rebuild_has_stable_chunk_ids(tmp_path: Path) -> None:
    index = SessionFileIndex(tmp_path, FakeEmbeddingAdapter(dimension=8))
    content = "# 概览\n\n状态图管理回合。\n\n# 限制\n\n递归预算需要有界。"
    first = index.index_attachment("user", "conversation", "file", "guide.md", content)
    second = index.index_attachment("user", "conversation", "file", "guide.md", content)

    assert first.indexed_chunks > 0
    assert second.indexed_chunks == 0
    assert second.skipped_chunks == first.indexed_chunks


def test_removed_attachment_is_not_returned_for_future_search(tmp_path: Path) -> None:
    index = SessionFileIndex(tmp_path, FakeEmbeddingAdapter(dimension=8))
    index.index_attachment(
        "user", "conversation", "file", "guide.md", "状态图管理回合。"
    )
    before = index.search("user", "conversation", ("file",), "状态图")

    index.remove_attachment("user", "conversation", "file")

    assert before
    assert index.search("user", "conversation", ("file",), "状态图") == ()
