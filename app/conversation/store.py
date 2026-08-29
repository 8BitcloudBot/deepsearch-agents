"""SQLite persistence for users, conversations, turns, attachments, and reports."""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.conversation.contracts import TurnResult

Role = Literal["admin", "user"]

# G13：最小迁移机制。v1 = 初始建表；后续 schema 变更以幂等步骤追加在
# _MIGRATIONS 中，既有库按 schema_state 记录的版本逐级演进。
_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class User:
    id: str
    username: str
    role: Role


@dataclass(frozen=True)
class AdminUserSummary:
    id: str
    username: str
    role: Role
    conversation_count: int


@dataclass(frozen=True)
class Conversation:
    id: str
    owner_id: str
    title: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Attachment:
    id: str
    conversation_id: str
    name: str
    stored_path: str
    size: int
    media_type: str
    active: bool


@dataclass(frozen=True)
class Turn:
    id: str
    conversation_id: str
    question: str
    answer: str | None
    use_web: bool
    status: str
    attachment_ids: tuple[str, ...]
    result: dict[str, object] | None
    created_at: str
    completed_at: str | None


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def _password_hash(password: str, *, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${derived.hex()}"


def _password_matches(password: str, encoded: str) -> bool:
    try:
        scheme, salt_hex, expected_hex = encoded.split("$", 2)
        if scheme != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=2**14,
            r=8,
            p=1,
        )
        return hmac.compare_digest(actual.hex(), expected_hex)
    except (ValueError, TypeError):
        return False


class ConversationStore:
    """Deep persistence module; callers operate on domain values, not SQL rows."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        # WS 读 + 回合写并发下避免立即抛 database is locked（H2；
        # 仅连接参数，不改存储语义）
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS attachments (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES
                        conversations(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    media_type TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    removed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS turns (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES
                        conversations(id) ON DELETE CASCADE,
                    question TEXT NOT NULL,
                    answer TEXT,
                    use_web INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    attachment_ids_json TEXT NOT NULL,
                    result_json TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS reports (
                    conversation_id TEXT PRIMARY KEY REFERENCES
                        conversations(id) ON DELETE CASCADE,
                    path TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            self._migrate(connection)
            for username, role in (("admin", "admin"), ("user", "user")):
                connection.execute(
                    "INSERT OR IGNORE INTO users(id, username, password_hash, role, "
                    "created_at) VALUES (?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), username, _password_hash("0000"), role, _now()),
                )

    def _migrate(self, connection: sqlite3.Connection) -> None:
        """幂等迁移：schema_state 记录版本，缺失的存量库视为 v1（初始建表）。"""
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_state (version INTEGER NOT NULL)"
        )
        row = connection.execute("SELECT version FROM schema_state").fetchone()
        if row is None:
            connection.execute("INSERT INTO schema_state(version) VALUES (1)")
            current = 1
        else:
            current = int(row["version"])
        migrations: dict[int, tuple[str, ...]] = {
            2: (
                "CREATE INDEX IF NOT EXISTS idx_conversations_owner "
                "ON conversations(owner_id)",
                "CREATE INDEX IF NOT EXISTS idx_turns_conversation "
                "ON turns(conversation_id)",
                "CREATE INDEX IF NOT EXISTS idx_attachments_conversation "
                "ON attachments(conversation_id)",
                "CREATE INDEX IF NOT EXISTS idx_auth_sessions_expiry "
                "ON auth_sessions(expires_at)",
            ),
        }
        for version in range(current + 1, _SCHEMA_VERSION + 1):
            for statement in migrations.get(version, ()):
                connection.execute(statement)
            connection.execute(
                "UPDATE schema_state SET version = ?", (version,)
            )

    def authenticate(self, username: str, password: str) -> User | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, username, password_hash, role "
                "FROM users WHERE username = ?",
                (username.strip(),),
            ).fetchone()
        if row is None or not _password_matches(password, row["password_hash"]):
            return None
        return User(id=row["id"], username=row["username"], role=row["role"])

    def admin_user_summaries(self, actor: User) -> tuple[AdminUserSummary, ...]:
        self._require_admin(actor)
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT users.id, users.username, users.role,
                    COUNT(conversations.id) AS conversation_count
                FROM users LEFT JOIN conversations ON conversations.owner_id = users.id
                GROUP BY users.id, users.username, users.role
                ORDER BY users.username"""
            ).fetchall()
        return tuple(
            AdminUserSummary(
                id=row["id"],
                username=row["username"],
                role=row["role"],
                conversation_count=int(row["conversation_count"]),
            )
            for row in rows
        )

    def all_conversation_ids(self) -> tuple[str, ...]:
        """全部会话 id（无权限维度，仅供服务端内部对账维护使用）。"""
        with self._connect() as connection:
            rows = connection.execute("SELECT id FROM conversations").fetchall()
        return tuple(row["id"] for row in rows)

    def admin_conversation_ids(self, actor: User, user_id: str) -> tuple[str, ...]:
        """admin 视角列出目标用户的会话 id（供清理 SQLite 之外的外置资产）。"""
        self._require_admin(actor)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id FROM conversations WHERE owner_id = ?", (user_id,)
            ).fetchall()
        return tuple(row["id"] for row in rows)

    def admin_delete_user_data(self, actor: User, user_id: str) -> None:
        self._require_admin(actor)
        if actor.id == user_id:
            raise ValueError("administrator data cannot be deleted here")
        with self._connect() as connection:
            paths = connection.execute(
                """SELECT attachments.stored_path FROM attachments
                JOIN conversations ON conversations.id = attachments.conversation_id
                WHERE conversations.owner_id = ?""",
                (user_id,),
            ).fetchall()
            connection.execute(
                "DELETE FROM conversations WHERE owner_id = ?", (user_id,)
            )
            connection.execute(
                "DELETE FROM auth_sessions WHERE user_id = ?", (user_id,)
            )
        for row in paths:
            path = Path(row["stored_path"])
            if path.is_file():
                path.unlink()

    def create_session(self, user: User, *, ttl_days: int = 7) -> str:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        expires = dt.datetime.now(dt.UTC) + dt.timedelta(days=ttl_days)
        with self._connect() as connection:
            # 顺带清理过期会话行（H2）：过期行此前只在原 token 再访问时惰性删除
            connection.execute(
                "DELETE FROM auth_sessions WHERE expires_at <= ?",
                (dt.datetime.now(dt.UTC).isoformat(),),
            )
            connection.execute(
                "INSERT INTO auth_sessions(token_hash, user_id, expires_at) "
                "VALUES (?, ?, ?)",
                (token_hash, user.id, expires.isoformat()),
            )
        return token

    def resolve_session(self, token: str | None) -> User | None:
        if not token:
            return None
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._connect() as connection:
            row = connection.execute(
                """SELECT users.id, users.username, users.role, auth_sessions.expires_at
                FROM auth_sessions JOIN users ON users.id = auth_sessions.user_id
                WHERE auth_sessions.token_hash = ?""",
                (token_hash,),
            ).fetchone()
            if row is None:
                return None
            if dt.datetime.fromisoformat(row["expires_at"]) <= dt.datetime.now(dt.UTC):
                connection.execute(
                    "DELETE FROM auth_sessions WHERE token_hash = ?", (token_hash,)
                )
                return None
        return User(id=row["id"], username=row["username"], role=row["role"])

    def delete_session(self, token: str) -> None:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM auth_sessions WHERE token_hash = ?", (token_hash,)
            )

    def create_conversation(self, user: User, title: str = "新研究") -> Conversation:
        title = self._title(title)
        now = _now()
        conversation = Conversation(str(uuid.uuid4()), user.id, title, now, now)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO conversations(id, owner_id, title, created_at, "
                "updated_at) VALUES (?, ?, ?, ?, ?)",
                (conversation.id, conversation.owner_id, title, now, now),
            )
        return conversation

    def list_conversations(self, user: User) -> tuple[Conversation, ...]:
        query = "SELECT * FROM conversations"
        params: tuple[object, ...] = ()
        if user.role != "admin":
            query += " WHERE owner_id = ?"
            params = (user.id,)
        query += " ORDER BY updated_at DESC, id DESC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return tuple(self._conversation(row) for row in rows)

    def get_conversation(self, user: User, conversation_id: str) -> Conversation:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
        if row is None or (user.role != "admin" and row["owner_id"] != user.id):
            raise LookupError("conversation not found")
        return self._conversation(row)

    def rename_conversation(
        self, user: User, conversation_id: str, title: str
    ) -> Conversation:
        self.get_conversation(user, conversation_id)
        now = _now()
        with self._connect() as connection:
            connection.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (self._title(title), now, conversation_id),
            )
        return self.get_conversation(user, conversation_id)

    def auto_title_conversation(
        self, user: User, conversation_id: str, question: str
    ) -> Conversation:
        current = self.get_conversation(user, conversation_id)
        if current.title != "新研究":
            return current
        title = re.sub(
            r"^(?:请问|我想(?:了解|研究|知道)|帮我(?:了解|研究))\s*",
            "",
            question.strip(),
        )
        title = re.sub(r"[？?。！!]+$", "", title).strip()
        if len(title) > 36:
            title = f"{title[:35].rstrip()}…"
        if not title:
            return current
        now = _now()
        with self._connect() as connection:
            connection.execute(
                """UPDATE conversations SET title = ?, updated_at = ?
                WHERE id = ? AND title = '新研究'""",
                (title, now, conversation_id),
            )
        return self.get_conversation(user, conversation_id)

    def delete_conversation(self, user: User, conversation_id: str) -> None:
        self.get_conversation(user, conversation_id)
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM conversations WHERE id = ?", (conversation_id,)
            )

    def add_attachment(
        self,
        user: User,
        conversation_id: str,
        *,
        name: str,
        stored_path: str,
        size: int,
        media_type: str,
    ) -> Attachment:
        self.get_conversation(user, conversation_id)
        attachment = Attachment(
            str(uuid.uuid4()),
            conversation_id,
            name,
            stored_path,
            size,
            media_type,
            True,
        )
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO attachments(id, conversation_id, name, stored_path, "
                "size, media_type, active, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                (
                    attachment.id,
                    conversation_id,
                    name,
                    stored_path,
                    size,
                    media_type,
                    _now(),
                ),
            )
        return attachment

    def list_attachments(
        self, user: User, conversation_id: str, *, active_only: bool = True
    ) -> tuple[Attachment, ...]:
        self.get_conversation(user, conversation_id)
        query = "SELECT * FROM attachments WHERE conversation_id = ?"
        if active_only:
            query += " AND active = 1"
        query += " ORDER BY created_at, id"
        with self._connect() as connection:
            rows = connection.execute(query, (conversation_id,)).fetchall()
        return tuple(self._attachment(row) for row in rows)

    def get_attachments_by_ids(
        self, attachment_ids: tuple[str, ...]
    ) -> tuple[Attachment, ...]:
        """Resolve active attachment snapshots without exposing SQL rows."""
        if not attachment_ids:
            return ()
        placeholders = ",".join("?" for _ in attachment_ids)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM attachments WHERE active = 1 "
                f"AND id IN ({placeholders})",
                attachment_ids,
            ).fetchall()
        by_id = {row["id"]: self._attachment(row) for row in rows}
        return tuple(by_id[item] for item in attachment_ids if item in by_id)

    def get_attachments_by_ids_scoped(
        self,
        user: User,
        conversation_id: str,
        attachment_ids: tuple[str, ...],
    ) -> tuple[Attachment, ...]:
        """Resolve active files only inside the authorized conversation namespace."""
        self.get_conversation(user, conversation_id)
        if not attachment_ids:
            return ()
        placeholders = ",".join("?" for _ in attachment_ids)
        with self._connect() as connection:
            rows = connection.execute(
                f"""SELECT * FROM attachments
                WHERE active = 1 AND conversation_id = ? AND id IN ({placeholders})""",
                (conversation_id, *attachment_ids),
            ).fetchall()
        by_id = {row["id"]: self._attachment(row) for row in rows}
        return tuple(by_id[item] for item in attachment_ids if item in by_id)

    def remove_attachment(
        self, user: User, conversation_id: str, attachment_id: str
    ) -> Attachment:
        self.get_conversation(user, conversation_id)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM attachments WHERE id = ? AND conversation_id = ?",
                (attachment_id, conversation_id),
            ).fetchone()
            if row is None:
                raise LookupError("attachment not found")
            connection.execute(
                "UPDATE attachments SET active = 0, removed_at = ? WHERE id = ?",
                (_now(), attachment_id),
            )
        return Attachment(
            row["id"],
            row["conversation_id"],
            row["name"],
            row["stored_path"],
            row["size"],
            row["media_type"],
            False,
        )

    def start_turn(
        self, user: User, conversation_id: str, *, question: str, use_web: bool
    ) -> Turn:
        self.get_conversation(user, conversation_id)
        question = question.strip()
        if not question or len(question) > 10000 or type(use_web) is not bool:
            raise ValueError("turn input is invalid")
        attachment_ids = tuple(
            item.id for item in self.list_attachments(user, conversation_id)
        )
        turn = Turn(
            str(uuid.uuid4()),
            conversation_id,
            question,
            None,
            use_web,
            "running",
            attachment_ids,
            None,
            _now(),
            None,
        )
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO turns(id, conversation_id, question, use_web, status, "
                "attachment_ids_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    turn.id,
                    conversation_id,
                    question,
                    int(use_web),
                    turn.status,
                    json.dumps(attachment_ids),
                    turn.created_at,
                ),
            )
            connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (turn.created_at, conversation_id),
            )
        return turn

    def get_turn(self, user: User, conversation_id: str, turn_id: str) -> Turn:
        self.get_conversation(user, conversation_id)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM turns WHERE id = ? AND conversation_id = ?",
                (turn_id, conversation_id),
            ).fetchone()
        if row is None:
            raise LookupError("turn not found")
        return self._turn(row)

    def list_turns(self, user: User, conversation_id: str) -> tuple[Turn, ...]:
        self.get_conversation(user, conversation_id)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM turns WHERE conversation_id = ? ORDER BY created_at, id",
                (conversation_id,),
            ).fetchall()
        return tuple(self._turn(row) for row in rows)

    def complete_turn(
        self,
        user: User,
        conversation_id: str,
        turn_id: str,
        result: TurnResult,
    ) -> Turn:
        current = self.get_turn(user, conversation_id, turn_id)
        if current.status != "running":
            raise ValueError("turn is already terminal")
        completed_at = _now()
        payload = json.dumps(
            result.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        with self._connect() as connection:
            connection.execute(
                """UPDATE turns
                SET answer = ?, status = 'completed', result_json = ?, completed_at = ?
                WHERE id = ?""",
                (result.answer, payload, completed_at, turn_id),
            )
            connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (completed_at, conversation_id),
            )
        return self.get_turn(user, conversation_id, turn_id)

    def fail_turn(
        self,
        user: User,
        conversation_id: str,
        turn_id: str,
        safe_message: str,
    ) -> Turn:
        current = self.get_turn(user, conversation_id, turn_id)
        if current.status != "running":
            return current
        completed_at = _now()
        failure = json.dumps(
            {"schema_version": "5.0.0", "error": safe_message},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        with self._connect() as connection:
            connection.execute(
                """UPDATE turns SET status = 'failed', result_json = ?, completed_at = ?
                WHERE id = ?""",
                (failure, completed_at, turn_id),
            )
        return self.get_turn(user, conversation_id, turn_id)

    def fail_stale_running_turns(self, *, max_age_seconds: int = 1800) -> int:
        """回收僵尸 running 回合（G4）：进程崩溃/重启后失去执行者的回合
        会永久停留 running；按创建时刻超过阈值收敛为 failed，恢复正常
        状态机语义。返回回收数量。
        """
        cutoff = (
            dt.datetime.now(dt.UTC) - dt.timedelta(seconds=max_age_seconds)
        ).isoformat()
        failure = json.dumps(
            {"schema_version": "5.0.0", "error": "服务中断，本轮研究未完成。"},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE turns SET status = 'failed', result_json = ?, completed_at = ?
                WHERE status = 'running' AND created_at <= ?""",
                (failure, _now(), cutoff),
            )
            return int(cursor.rowcount)

    def record_report(
        self,
        user: User,
        conversation_id: str,
        *,
        path: str,
        checksum: str,
    ) -> None:
        self.get_conversation(user, conversation_id)
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO reports(conversation_id, path, checksum, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(conversation_id) DO UPDATE SET
                    path = excluded.path,
                    checksum = excluded.checksum,
                    updated_at = excluded.updated_at""",
                (conversation_id, path, checksum, _now()),
            )

    def report_path(self, user: User, conversation_id: str) -> str | None:
        self.get_conversation(user, conversation_id)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT path FROM reports WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
        return row["path"] if row else None

    @staticmethod
    def _title(value: str) -> str:
        title = value.strip()
        if not title or len(title) > 120:
            raise ValueError("conversation title is invalid")
        return title

    @staticmethod
    def _require_admin(user: User) -> None:
        if user.role != "admin":
            raise PermissionError("administrator access required")

    @staticmethod
    def _conversation(row: sqlite3.Row) -> Conversation:
        return Conversation(
            row["id"],
            row["owner_id"],
            row["title"],
            row["created_at"],
            row["updated_at"],
        )

    @staticmethod
    def _attachment(row: sqlite3.Row) -> Attachment:
        return Attachment(
            row["id"],
            row["conversation_id"],
            row["name"],
            row["stored_path"],
            row["size"],
            row["media_type"],
            bool(row["active"]),
        )

    @staticmethod
    def _turn(row: sqlite3.Row) -> Turn:
        return Turn(
            row["id"],
            row["conversation_id"],
            row["question"],
            row["answer"],
            bool(row["use_web"]),
            row["status"],
            tuple(json.loads(row["attachment_ids_json"])),
            json.loads(row["result_json"]) if row["result_json"] else None,
            row["created_at"],
            row["completed_at"],
        )
