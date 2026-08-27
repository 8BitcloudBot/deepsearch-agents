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
_HISTORY_CHAR_BUDGET = 12000


class ConversationApplication:
    def __init__(
        self,
        store: ConversationStore,
        engine: TurnResearchEngine,
        report: ConversationReport,
        capabilities: dict[str, dict[str, str]] | None = None,
        upload_store: Any | None = None,
    ) -> None:
        self.store = store
        self.engine = engine
        self.report = report
        # session_file 能力键保留以维持 WS capabilities 合同稳定；
        # 会话附件路径已由知识库入库方案取代（T1），恒为 unavailable。
        self.capabilities = capabilities or {
            source: {"status": "unavailable"}
            for source in ("model", "knowledge", "web", "session_file")
        }
        self._turn_locks: dict[tuple[str, str], asyncio.Lock] = {}
        self.upload_store = upload_store

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
            user_knowledge = None
            if self.upload_store is not None:
                try:
                    user_knowledge = self.upload_store.retriever_for(user.id)
                except Exception:
                    user_knowledge = None
            result = await self.engine.run(input_value, user_knowledge=user_knowledge)
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
