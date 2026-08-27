import sqlite3
from pathlib import Path

from app.conversation.contracts import Claim, EvidenceItem, TurnResult
from app.conversation.store import ConversationStore


def store(tmp_path: Path) -> ConversationStore:
    return ConversationStore(tmp_path / "reasonix.sqlite3")


def test_store_seeds_hashed_demo_accounts_and_authenticates(tmp_path: Path) -> None:
    repository = store(tmp_path)

    admin = repository.authenticate("admin", "0000")
    user = repository.authenticate("user", "0000")

    assert admin is not None and admin.role == "admin"
    assert user is not None and user.role == "user"
    assert repository.authenticate("user", "wrong") is None
    with sqlite3.connect(tmp_path / "reasonix.sqlite3") as connection:
        hashes = [
            row[0] for row in connection.execute("SELECT password_hash FROM users")
        ]
    assert hashes and all(
        value != "0000" and value.startswith("scrypt$") for value in hashes
    )


def test_user_only_lists_own_conversations_but_admin_lists_all(tmp_path: Path) -> None:
    repository = store(tmp_path)
    admin = repository.authenticate("admin", "0000")
    user = repository.authenticate("user", "0000")
    assert admin is not None and user is not None

    own = repository.create_conversation(user, "我的研究")
    repository.create_conversation(admin, "管理员研究")

    assert [item.id for item in repository.list_conversations(user)] == [own.id]
    assert {item.title for item in repository.list_conversations(admin)} == {
        "我的研究",
        "管理员研究",
    }


def test_session_tokens_resolve_without_storing_the_raw_token(tmp_path: Path) -> None:
    repository = store(tmp_path)
    user = repository.authenticate("user", "0000")
    assert user is not None

    token = repository.create_session(user)

    assert repository.resolve_session(token) == user
    with sqlite3.connect(tmp_path / "reasonix.sqlite3") as connection:
        stored = connection.execute("SELECT token_hash FROM auth_sessions").fetchone()
    assert stored is not None and stored[0] != token
    repository.delete_session(token)
    assert repository.resolve_session(token) is None


def test_removed_attachment_stays_on_completed_turn_but_not_future_turns(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    user = repository.authenticate("user", "0000")
    assert user is not None
    conversation = repository.create_conversation(user, "文件研究")
    attachment = repository.add_attachment(
        user,
        conversation.id,
        name="notes.md",
        stored_path="uploads/notes.md",
        size=12,
        media_type="text/markdown",
    )

    first = repository.start_turn(
        user,
        conversation.id,
        question="第一问",
        use_web=False,
    )
    assert first.attachment_ids == (attachment.id,)

    repository.remove_attachment(user, conversation.id, attachment.id)
    second = repository.start_turn(
        user,
        conversation.id,
        question="第二问",
        use_web=True,
    )

    assert repository.get_turn(user, conversation.id, first.id).attachment_ids == (
        attachment.id,
    )
    assert second.attachment_ids == ()


def test_attachment_lookup_by_ids_returns_only_existing_records(tmp_path: Path) -> None:
    repository = store(tmp_path)
    user = repository.authenticate("user", "0000")
    assert user is not None
    conversation = repository.create_conversation(user, "文件")
    item = repository.add_attachment(
        user,
        conversation.id,
        name="notes.md",
        stored_path="/tmp/notes.md",
        size=1,
        media_type="text/markdown",
    )

    found = repository.get_attachments_by_ids((item.id, "missing"))

    assert tuple(record.id for record in found) == (item.id,)


def test_scoped_attachment_lookup_cannot_cross_conversation_or_user(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    user = repository.authenticate("user", "0000")
    assert user is not None
    first = repository.create_conversation(user, "第一会话")
    second = repository.create_conversation(user, "第二会话")
    item = repository.add_attachment(
        user,
        first.id,
        name="private.md",
        stored_path="/tmp/private.md",
        size=1,
        media_type="text/markdown",
    )

    assert repository.get_attachments_by_ids_scoped(user, first.id, (item.id,)) == (
        item,
    )
    assert repository.get_attachments_by_ids_scoped(user, second.id, (item.id,)) == ()


def test_rename_and_delete_require_conversation_access(tmp_path: Path) -> None:
    repository = store(tmp_path)
    admin = repository.authenticate("admin", "0000")
    user = repository.authenticate("user", "0000")
    assert admin is not None and user is not None
    conversation = repository.create_conversation(user, "原始标题")

    renamed = repository.rename_conversation(user, conversation.id, "新标题")
    assert renamed.title == "新标题"

    repository.delete_conversation(admin, conversation.id)
    assert repository.list_conversations(user) == ()


def test_auto_title_only_replaces_the_default_title(tmp_path: Path) -> None:
    repository = store(tmp_path)
    user = repository.authenticate("user", "0000")
    assert user is not None
    automatic = repository.create_conversation(user)
    manual = repository.create_conversation(user, "我的手动标题")

    titled = repository.auto_title_conversation(
        user,
        automatic.id,
        "我想了解 LangGraph 的状态和持久化应该怎么入门？",
    )
    preserved = repository.auto_title_conversation(
        user,
        manual.id,
        "这条问题不应该覆盖手动标题",
    )

    assert titled.title == "LangGraph 的状态和持久化应该怎么入门"
    assert preserved.title == "我的手动标题"


def test_completed_turn_persists_schema_5_result(tmp_path: Path) -> None:
    repository = store(tmp_path)
    user = repository.authenticate("user", "0000")
    assert user is not None
    conversation = repository.create_conversation(user, "持久化研究")
    turn = repository.start_turn(user, conversation.id, question="问题", use_web=False)
    item = EvidenceItem(
        evidence_id="ev-1",
        source_kind="knowledge",
        title="官方文档",
        locator_kind="chunk",
        locator_value="doc.md#start",
        quote="证据原文",
    )
    result = TurnResult(
        schema_version="5.0.0",
        answer="回答。[1]",
        claims=(Claim("claim-1", "结论", ("ev-1",)),),
        evidence=(item,),
        limitations=(),
    )

    completed = repository.complete_turn(user, conversation.id, turn.id, result)

    assert completed.status == "completed"
    assert completed.answer == "回答。[1]"
    assert completed.result == result.as_dict()
