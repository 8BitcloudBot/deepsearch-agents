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


def test_new_turns_no_longer_fill_dead_attachment_pipeline(
    tmp_path: Path,
) -> None:
    """I1 冻结语义：T1 移除附件端点后新回合恒空；attachments 表与历史
    行读取保留（存储合同不变），add_attachment 仅可经 store 直接构造
    模拟存量数据。"""
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

    new_turn = repository.start_turn(
        user,
        conversation.id,
        question="第一问",
        use_web=False,
    )
    # I1：新回合不再填充附件 id（死数据流水线关闭）
    assert new_turn.attachment_ids == ()

    # 历史行（手工写入存量形态）读取兼容：attachment_ids 仍可解析
    import json as _json

    with repository._connect() as connection:
        connection.execute(
            "UPDATE turns SET attachment_ids_json = ? WHERE id = ?",
            (_json.dumps([attachment.id]), new_turn.id),
        )
    assert repository.get_turn(user, conversation.id, new_turn.id).attachment_ids == (
        attachment.id,
    )


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


def test_admin_conversation_ids_lists_target_user_conversations(tmp_path) -> None:
    import pytest

    repository = ConversationStore(tmp_path / "state.sqlite3")
    admin = repository.authenticate("admin", "0000")
    user = repository.authenticate("user", "0000")
    assert admin is not None and user is not None
    first = repository.create_conversation(user, "会话一")
    repository.create_conversation(user, "会话二")
    ids = repository.admin_conversation_ids(admin, user.id)
    assert first.id in ids and len(ids) == 2
    with pytest.raises(PermissionError):
        repository.admin_conversation_ids(user, user.id)


def test_fail_stale_running_turns_reclaims_only_expired(tmp_path) -> None:
    repository = ConversationStore(tmp_path / "state.sqlite3")
    user = repository.authenticate("user", "0000")
    assert user is not None
    conversation = repository.create_conversation(user, "僵尸回收")
    stale = repository.start_turn(user, conversation.id, question="旧的", use_web=False)
    fresh = repository.start_turn(user, conversation.id, question="新的", use_web=False)

    # 新鲜回合（阈值内）不受影响
    assert repository.fail_stale_running_turns(max_age_seconds=3600) == 0
    assert repository.get_turn(user, conversation.id, stale.id).status == "running"

    # 阈值归零：创建时刻必然早于截止线，全部 running 收敛为 failed
    assert repository.fail_stale_running_turns(max_age_seconds=0) == 2
    reclaimed = repository.get_turn(user, conversation.id, stale.id)
    assert reclaimed.status == "failed"
    assert reclaimed.completed_at is not None
    assert repository.get_turn(user, conversation.id, fresh.id).status == "failed"
    # 幂等：已终态的回合不再被触碰
    assert repository.fail_stale_running_turns(max_age_seconds=0) == 0


def test_schema_migration_creates_indexes_and_tracks_version(tmp_path) -> None:
    import sqlite3

    repository = ConversationStore(tmp_path / "state.sqlite3")
    with sqlite3.connect(repository.path) as connection:
        version = connection.execute("SELECT version FROM schema_state").fetchone()[0]
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'index' AND name LIKE 'idx_%'"
            )
        }
    assert version == 2
    assert {
        "idx_conversations_owner",
        "idx_turns_conversation",
        "idx_attachments_conversation",
        "idx_auth_sessions_expiry",
    } <= names


def test_schema_migration_upgrades_legacy_database(tmp_path) -> None:
    import sqlite3

    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        # 手造 v1 存量库：有业务表但无 schema_state 与索引
        connection.executescript(
            """
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE conversations (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE turns (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT,
                use_web INTEGER NOT NULL,
                status TEXT NOT NULL,
                attachment_ids_json TEXT NOT NULL,
                result_json TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT
            );
            """
        )
    ConversationStore(path)  # 打开即迁移
    with sqlite3.connect(path) as connection:
        version = connection.execute("SELECT version FROM schema_state").fetchone()[0]
        indexes = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'index' AND name LIKE 'idx_%'"
            )
        }
    assert version == 2
    assert "idx_turns_conversation" in indexes


def test_busy_timeout_pragma_is_set(tmp_path) -> None:
    repository = ConversationStore(tmp_path / "state.sqlite3")
    with repository._connect() as connection:
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_create_session_purges_expired_rows(tmp_path) -> None:
    import sqlite3

    repository = ConversationStore(tmp_path / "state.sqlite3")
    user = repository.authenticate("user", "0000")
    assert user is not None
    stale = repository.create_session(user)
    fresh = repository.create_session(user)
    with sqlite3.connect(repository.path) as connection:
        connection.execute(
            "UPDATE auth_sessions SET expires_at = '2000-01-01T00:00:00+00:00' "
            "WHERE token_hash = ?",
            (__import__("hashlib").sha256(stale.encode("utf-8")).hexdigest(),),
        )
    repository.create_session(user)  # 触发顺带清理
    with sqlite3.connect(repository.path) as connection:
        remaining = {
            row[0] for row in connection.execute("SELECT token_hash FROM auth_sessions")
        }
    stale_hash = __import__("hashlib").sha256(stale.encode("utf-8")).hexdigest()
    fresh_hash = __import__("hashlib").sha256(fresh.encode("utf-8")).hexdigest()
    assert stale_hash not in remaining
    assert fresh_hash in remaining
