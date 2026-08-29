"""Deterministic cumulative Markdown report for a conversation."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
from pathlib import Path

from app.conversation.contracts import EvidenceItem, TurnResult
from app.conversation.store import ConversationStore, Turn, User


class ConversationReport:
    def __init__(self, root: str | Path, store: ConversationStore):
        self._root = Path(root)
        self._store = store

    def refresh(self, user: User, conversation_id: str) -> Path:
        conversation = self._store.get_conversation(user, conversation_id)
        completed = tuple(
            turn
            for turn in self._store.list_turns(user, conversation_id)
            if turn.status == "completed" and turn.result is not None
        )
        markdown = _render(
            conversation.title,
            conversation.created_at,
            conversation.updated_at,
            completed,
        )
        target = self._root / conversation_id / "research-report.md"
        _atomic_write(target, markdown.encode("utf-8"))
        self._store.record_report(
            user,
            conversation_id,
            # 存相对路径：报告根目录迁移后记录不失效（G3 数据完整性）
            path=str(target.relative_to(self._root)),
            checksum=hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
        )
        return target

    def discard(self, user: User, conversation_id: str) -> None:
        """删除会话时移除其报告目录；会话不存在时由 store 抛 LookupError。"""
        self._store.get_conversation(user, conversation_id)
        shutil.rmtree(self._root / conversation_id, ignore_errors=True)


def _render(
    title: str,
    created_at: str,
    updated_at: str,
    turns: tuple[Turn, ...],
) -> str:
    lines = [
        f"# {title}",
        "",
        f"- 创建时间：{created_at}",
        f"- 更新时间：{updated_at}",
        f"- 已完成回合：{len(turns)}",
        "",
    ]
    if not turns:
        lines.extend(("当前尚无已完成的研究回合。", ""))
        return "\n".join(lines)

    source_turns: dict[str, list[int]] = {}
    source_items: dict[str, EvidenceItem] = {}
    turn_results: list[tuple[Turn, TurnResult]] = []
    for turn_number, turn in enumerate(turns, start=1):
        result = TurnResult.from_dict(turn.result)
        turn_results.append((turn, result))
        evidence_by_id = {item.evidence_id: item for item in result.evidence}
        cited_ids = tuple(
            dict.fromkeys(
                evidence_id
                for claim in result.claims
                for evidence_id in claim.evidence_ids
            )
        )
        for evidence_id in cited_ids:
            item = evidence_by_id[evidence_id]
            source_key = _source_key(item)
            source_items.setdefault(source_key, item)
            source_turns.setdefault(source_key, [])
            if turn_number not in source_turns[source_key]:
                source_turns[source_key].append(turn_number)

    source_numbers = {
        source_key: index for index, source_key in enumerate(source_items, start=1)
    }
    for turn_number, (turn, result) in enumerate(turn_results, start=1):
        evidence_by_id = {item.evidence_id: item for item in result.evidence}
        local_to_global = {
            index: source_numbers[_source_key(item)]
            for index, item in enumerate(result.evidence, start=1)
            if _source_key(item) in source_numbers
        }
        limit_lines = (
            [f"- {limitation}" for limitation in result.limitations]
            if result.limitations
            else ["- 暂无明确限制。"]
        )
        lines.extend(
            [
                f"## 第 {turn_number} 轮：{turn.question}",
                "",
                "### 本轮限制",
                "",
                *limit_lines,
                "",
                "### 回答",
                "",
                _remap_answer_citations(result.answer, local_to_global),
                "",
                "### 结论依据",
                "",
            ]
        )
        for claim_number, claim in enumerate(result.claims, start=1):
            refs = "、".join(
                f"[{source_numbers[_source_key(evidence_by_id[evidence_id])]}]"
                for evidence_id in claim.evidence_ids
                if evidence_id in evidence_by_id
            )
            lines.append(f"{claim_number}. {claim.statement}（证据 {refs}）")
        lines.append("")

    lines.extend(("## 证据附录（累计来源索引）", ""))
    for source_key, item in source_items.items():
        index = source_numbers[source_key]
        _append_evidence(lines, item, index, source_turns[source_key])
    return "\n".join(lines)


def _source_key(item: EvidenceItem) -> str:
    return f"{item.source_kind}|{item.locator_value.casefold()}"


def _remap_answer_citations(answer: str, local_to_global: dict[int, int]) -> str:
    return re.sub(
        r"\[(\d+)\]",
        lambda match: (
            f"[{local_to_global[int(match.group(1))]}]"
            if int(match.group(1)) in local_to_global
            else match.group(0)
        ),
        answer,
    )


def _append_evidence(
    lines: list[str], item: EvidenceItem, number: int, rounds: list[int]
) -> None:
    source_labels = {
        "knowledge": "本地知识库",
        "session_file": "会话文件",
        "web": "实时网络",
    }
    locator = (
        f"<{item.locator_value}>"
        if item.locator_kind == "url"
        else item.locator_value
    )
    hostname = f"；主机：{item.hostname}" if item.hostname else ""
    rounds_label = "、".join(str(value) for value in rounds)
    lines.extend(
        (
            f"### [{number}] {item.title}",
            "",
            f"- 来源：{source_labels[item.source_kind]}{hostname}",
            f"- 定位：{locator}",
            f"- 引用回合：{rounds_label}",
            f"> {item.quote}",
            "",
        )
    )


def _atomic_write(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        dir=target.parent, prefix=".report-", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
