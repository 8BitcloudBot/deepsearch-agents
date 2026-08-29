"""Application orchestration around the SQLite store and bounded turn graph."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from weakref import WeakValueDictionary

from app.conversation.model import safe_message_for
from app.conversation.report import ConversationReport
from app.conversation.store import ConversationStore, Turn, User
from app.conversation.turn import TurnExecutionError, TurnInput, TurnResearchEngine
from app.logging_setup import brief

EventEmitter = Callable[[dict[str, Any]], None]
_HISTORY_CHAR_BUDGET = 12000
logger = logging.getLogger("deepsearch.application")


class ConversationApplication:
    def __init__(
        self,
        store: ConversationStore,
        engine: TurnResearchEngine,
        report: ConversationReport,
        capabilities: dict[str, dict[str, str]] | None = None,
        upload_store: Any | None = None,
        *,
        stale_turn_seconds: int = 1800,
        max_turns_per_conversation: int = 0,
        title_generator: Any | None = None,
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
        # 弱值字典：锁仅在被等待/持有时存活，回合结束后自动回收，
        # 避免 (conversation, turn) 键随进程生命周期无限累积（G3）。
        self._turn_locks: WeakValueDictionary[
            tuple[str, str], asyncio.Lock
        ] = WeakValueDictionary()
        self.upload_store = upload_store
        self._stale_turn_seconds = stale_turn_seconds
        self._max_turns_per_conversation = max_turns_per_conversation
        self.title_generator = title_generator

    async def submit(
        self,
        user: User,
        conversation_id: str,
        *,
        question: str,
        use_web: bool,
    ) -> Turn:
        # 每次新建回合前回收僵尸 running 回合（进程崩溃/重启后的遗留状态）
        reclaimed = self.store.fail_stale_running_turns(
            max_age_seconds=self._stale_turn_seconds
        )
        if reclaimed:
            logger.warning("reclaimed %d stale running turn(s)", reclaimed)
        if self._max_turns_per_conversation:
            existing = self.store.list_turns(user, conversation_id)
            if len(existing) >= self._max_turns_per_conversation:
                raise ValueError("conversation turn limit reached")
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
        started_at = time.monotonic()
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
            result = await self.engine.run(
                input_value, user_knowledge=user_knowledge, emit=emit
            )
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
            renamed = False
            if self.title_generator is not None:
                try:
                    title = await self.title_generator.generate(turn.question)
                    renamed = self.store.rename_if_untitled(
                        user, conversation_id, title
                    )
                except Exception as exc:
                    logger.warning("model title generation failed: %s", brief(exc))
            if not renamed:
                self.store.auto_title_conversation(
                    user, conversation_id, turn.question
                )
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
            logger.info(
                "turn completed turn_id=%s elapsed=%.1fs",
                turn_id,
                time.monotonic() - started_at,
            )
            return completed
        except Exception as exc:
            logger.warning(
                "turn execution failed turn_id=%s elapsed=%.1fs: %s",
                turn_id,
                time.monotonic() - started_at,
                brief(exc),
            )
            if isinstance(exc, TurnExecutionError):
                # 红线3：用户面文案取自 model.py 稳定枚举；事件 data 新增
                # error_kind 供前端区分"重试即可"与"配置问题"（向后兼容）
                error_kind = exc.code
                safe_message = safe_message_for(exc.code)
            else:
                error_kind = None
                safe_message = "本轮研究未能完成，请稍后重试。"
            failed = self.store.fail_turn(
                user, conversation_id, turn_id, safe_message
            )
            emit(
                {
                    "type": "turn.failed",
                    "stage": "failed",
                    "message": safe_message,
                    "data": {
                        "turn_id": turn_id,
                        **({"error_kind": error_kind} if error_kind else {}),
                    },
                }
            )
            return failed


_SENTENCE_ENDINGS = "。！？!?；;"


def _truncate_at_sentence(text: str, limit: int) -> str:
    """按句子边界截断（G12）：注入三角色的历史不出现拦腰残句。

    从上限位置向前找最近的句末标点（中文为主，含英文 !?;）；找不到
    （或全文无标点）退化为原字符截断，保证预算上限依然成立。
    """
    if len(text) <= limit:
        return text
    clipped = text[:limit]
    for index in range(len(clipped) - 1, 0, -1):
        if clipped[index] in _SENTENCE_ENDINGS:
            return clipped[: index + 1]
    return clipped


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
        answer = _truncate_at_sentence(answer, available)
        selected.append((question, answer))
        used += len(question) + len(answer) + 1
    selected.reverse()
    return tuple(selected)
