"""Application orchestration around the SQLite store and bounded turn graph."""

from __future__ import annotations

import asyncio
import logging
import math
import re
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
_HISTORY_TOKEN_BUDGET = 12000  # 中文≈1 token/字，与原 12000 字符预算语义对齐（H11）
logger = logging.getLogger("deepsearch.application")


def _rollup_conclusions(
    excluded: tuple[tuple[str, str], ...], *, max_items: int = 6
) -> str:
    """B10-2 结论卡：窗口外更早轮次的确定性摘要（问题+答案首句）。

    纯拼装、无模型调用；为空时综合器 payload 不携带该字段语义。
    """
    if not excluded:
        return ""
    lines: list[str] = []
    for question, answer in excluded[-max_items:]:
        first_sentence = re.split(r"[。！？!?]", answer.strip())[0][:100]
        lines.append(f"- {question[:60]}：{first_sentence}")
    return "此前轮次已讨论（结论卡）：\n" + "\n".join(lines)


def _estimate_tokens(text: str) -> int:
    """加权 token 估算：CJK 每字计 1，其余按 4 字符≈1 token（H11）。"""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return cjk + math.ceil((len(text) - cjk) / 4)


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
        history_token_budget: int = _HISTORY_TOKEN_BUDGET,
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
        # 弱值字典：锁仅在被等待/持有时存活，回合结束后自动回收。
        # H13：锁粒度为会话级——同会话多个回合串行执行，避免并行回合
        # 互见的历史快照不一致与 updated_at 竞写。
        self._turn_locks: WeakValueDictionary[str, asyncio.Lock] = (
            WeakValueDictionary()
        )
        self.upload_store = upload_store
        self._stale_turn_seconds = stale_turn_seconds
        self._max_turns_per_conversation = max_turns_per_conversation
        self.title_generator = title_generator
        self._history_token_budget = history_token_budget

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
        lock = self._turn_locks.setdefault(conversation_id, asyncio.Lock())
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
        all_history = tuple(
            (item.question, item.answer or "")
            for item in self.store.list_turns(user, conversation_id)
            if item.status == "completed" and item.id != turn_id and item.answer
        )
        history = _bounded_history(all_history, budget=self._history_token_budget)
        # B10-2：窗口外更早轮次生成结论卡随回合注入综合器
        excluded = all_history[: max(0, len(all_history) - len(history))]
        input_value = TurnInput(
            question=turn.question,
            use_web=turn.use_web,
            attachment_ids=turn.attachment_ids,
            recent_history=history,
            prior_summary=_rollup_conclusions(excluded),
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
        except asyncio.CancelledError:
            # I5：用户取消——收敛为 failed 并发 turn.cancelled（BaseException
            # 子类，须在 except Exception 之前单独捕获）
            logger.info("turn cancelled turn_id=%s", turn_id)
            failed = self.store.fail_turn(
                user, conversation_id, turn_id, "本轮研究已取消。"
            )
            emit(
                {
                    "type": "turn.cancelled",
                    "stage": "failed",
                    "message": "本轮研究已取消。",
                    "data": {"turn_id": turn_id},
                }
            )
            return failed
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
    history: tuple[tuple[str, str], ...],
    *,
    budget: int = _HISTORY_TOKEN_BUDGET,
) -> tuple[tuple[str, str], ...]:
    """Keep the newest useful context under a deterministic token budget (H11).

    先按 token 估算换算 4×字符窗口粗截，CJK 占比高时二次按 1:1 收敛，
    保证总成本不超预算；中文场景与原字符预算行为基本一致。
    """
    selected: list[tuple[str, str]] = []
    used = 0
    for question, answer in reversed(history[-6:]):
        question = question[:2000]
        question_cost = _estimate_tokens(question)
        available = budget - used - question_cost - 1
        if available <= 0:
            break
        answer = _truncate_at_sentence(answer, available * 4)
        if _estimate_tokens(answer) > available:
            answer = _truncate_at_sentence(answer, available)
        selected.append((question, answer))
        used += question_cost + _estimate_tokens(answer) + 1
    selected.reverse()
    return tuple(selected)
