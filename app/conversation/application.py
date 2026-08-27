"""Application orchestration around the SQLite store and bounded turn graph."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.conversation.report import ConversationReport
from app.conversation.store import ConversationStore, Turn, User
from app.conversation.turn import TurnInput, TurnResearchEngine

EventEmitter = Callable[[dict[str, Any]], None]
SessionFileFactory = Callable[[User, str], Any]
_HISTORY_CHAR_BUDGET = 12000


class ConversationApplication:
    def __init__(
        self,
        store: ConversationStore,
        engine: TurnResearchEngine,
        report: ConversationReport,
        session_file_factory: SessionFileFactory | None = None,
        file_index: Any | None = None,
        capabilities: dict[str, dict[str, str]] | None = None,
    ) -> None:
        self.store = store
        self.engine = engine
        self.report = report
        self.capabilities = capabilities or {
            source: {"status": "unavailable"}
            for source in ("model", "knowledge", "web", "session_file")
        }
        self._session_file_factory = session_file_factory
        self._file_index = file_index
        self._turn_locks: dict[tuple[str, str], asyncio.Lock] = {}

    def index_attachment(
        self, user: User, conversation_id: str, attachment: Any
    ) -> None:
        if self._file_index is None:
            raise RuntimeError("session file index unavailable")
        self._file_index.index_attachment_path(
            user.id,
            conversation_id,
            attachment.id,
            attachment.name,
            attachment.stored_path,
        )

    def remove_attachment(
        self, user: User, conversation_id: str, attachment_id: str
    ) -> None:
        if self._file_index is not None:
            self._file_index.remove_attachment(user.id, conversation_id, attachment_id)

    async def submit(
        self,
        user: User,
        conversation_id: str,
        *,
        question: str,
        use_web: bool,
    ) -> Turn:
        return self.store.start_turn(
            user, conversation_id, question=question, use_web=use_web
        )

    async def execute(
        self,
        user: User,
        conversation_id: str,
        turn_id: str,
        *,
        emit: EventEmitter | None = None,
    ) -> Turn:
        lock = self._turn_locks.setdefault((conversation_id, turn_id), asyncio.Lock())
        async with lock:
            return await self._execute_once(user, conversation_id, turn_id, emit=emit)

    async def _execute_once(
        self,
        user: User,
        conversation_id: str,
        turn_id: str,
        *,
        emit: EventEmitter | None = None,
    ) -> Turn:
        emit = emit or (lambda event: None)
        turn = self.store.get_turn(user, conversation_id, turn_id)
        if turn.status != "running":
            return turn
        history = _bounded_history(
            tuple(
                (item.question, item.answer or "")
                for item in self.store.list_turns(user, conversation_id)
                if item.status == "completed" and item.id != turn_id and item.answer
            )
        )
        input_value = TurnInput(
            question=turn.question,
            use_web=turn.use_web,
            attachment_ids=turn.attachment_ids,
            recent_history=history,
        )
        emit({"type": "stage.changed", "stage": "planning", "message": "正在分析问题"})
        source_kinds = ["knowledge"]
        if turn.attachment_ids:
            source_kinds.append("session_file")
        if turn.use_web:
            source_kinds.append("web")
        emit(
            {
                "type": "stage.changed",
                "stage": "retrieval",
                "message": "正在检索证据",
                "data": {"source_kinds": source_kinds},
            }
        )
        try:
            if self._session_file_factory is not None:
                result = await self.engine.run(
                    input_value,
                    session_files=self._session_file_factory(user, conversation_id),
                )
            else:
                result = await self.engine.run(input_value)
            emit(
                {
                    "type": "stage.changed",
                    "stage": "synthesis",
                    "message": "正在整理回答",
                }
            )
            emit(
                {
                    "type": "answer.delta",
                    "stage": "synthesis",
                    "message": "回答已生成",
                    "data": {"text": result.answer},
                }
            )
            emit(
                {
                    "type": "evidence.ready",
                    "stage": "evidence",
                    "message": "证据已整理",
                    "data": {
                        "evidence_count": len(result.evidence),
                        "cited_evidence_count": len(
                            {
                                evidence_id
                                for claim in result.claims
                                for evidence_id in claim.evidence_ids
                            }
                        ),
                        "source_kinds": sorted(
                            {item.source_kind for item in result.evidence}
                        ),
                    },
                }
            )
            completed = self.store.complete_turn(user, conversation_id, turn_id, result)
            self.store.auto_title_conversation(user, conversation_id, turn.question)
            path = self.report.refresh(user, conversation_id)
            emit(
                {
                    "type": "report.updated",
                    "stage": "report",
                    "message": "研究报告已更新",
                    "data": {"report": Path(path).name},
                }
            )
            emit(
                {
                    "type": "turn.completed",
                    "stage": "completed",
                    "message": "本轮回答已完成",
                    "data": {"turn_id": turn_id},
                }
            )
            return completed
        except Exception:
            failed = self.store.fail_turn(
                user,
                conversation_id,
                turn_id,
                "本轮研究未能完成，请稍后重试。",
            )
            emit(
                {
                    "type": "turn.failed",
                    "stage": "failed",
                    "message": "本轮研究未能完成，请稍后重试。",
                    "data": {"turn_id": turn_id},
                }
            )
            return failed


def _bounded_history(
    history: tuple[tuple[str, str], ...], *, budget: int = _HISTORY_CHAR_BUDGET
) -> tuple[tuple[str, str], ...]:
    """Keep the newest useful context under a deterministic character budget."""
    selected: list[tuple[str, str]] = []
    used = 0
    for question, answer in reversed(history[-6:]):
        question = question[:2000]
        available = budget - used - len(question) - 1
        if available <= 0:
            break
        answer = answer[:available]
        selected.append((question, answer))
        used += len(question) + len(answer) + 1
    selected.reverse()
    return tuple(selected)
