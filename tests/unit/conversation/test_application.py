from dataclasses import dataclass
from pathlib import Path

import pytest

from app.conversation.application import ConversationApplication
from app.conversation.contracts import Claim, EvidenceItem, TurnResult
from app.conversation.report import ConversationReport
from app.conversation.store import ConversationStore


@dataclass
class Engine:
    seen: list[object]

    async def run(self, turn, *, user_knowledge=None, emit=None):
        self.seen.append(turn)
        item = EvidenceItem(
            evidence_id="ev-knowledge-1",
            source_kind="knowledge",
            title="知识文档",
            locator_kind="chunk",
            locator_value="guide.md#intro",
            quote="知识证据",
        )
        return TurnResult(
            schema_version="5.0.0",
            answer="完成回答。[1]",
            claims=(Claim("claim-1", "完成结论", (item.evidence_id,)),),
            evidence=(item,),
            limitations=(),
        )


@pytest.mark.asyncio
async def test_application_runs_turn_with_recent_history_and_refreshes_report(
    tmp_path: Path,
) -> None:
    store = ConversationStore(tmp_path / "reasonix.sqlite3")
    user = store.authenticate("user", "0000")
    assert user is not None
    conversation = store.create_conversation(user, "多轮研究")
    engine = Engine([])
    application = ConversationApplication(
        store,
        engine,
        ConversationReport(tmp_path / "reports", store),
    )

    first = await application.submit(
        user, conversation.id, question="第一问", use_web=False
    )
    await application.execute(user, conversation.id, first.id)
    second = await application.submit(
        user, conversation.id, question="追问", use_web=True
    )
    events = []
    await application.execute(user, conversation.id, second.id, emit=events.append)

    assert engine.seen[-1].recent_history == (("第一问", "完成回答。[1]"),)
    assert engine.seen[-1].use_web is True
    assert [event["type"] for event in events] == [
        "stage.changed",
        "stage.changed",
        "stage.changed",
        "answer.delta",
        "evidence.ready",
        "report.updated",
        "turn.completed",
    ]
    assert [event["stage"] for event in events[:3]] == [
        "planning",
        "retrieval",
        "synthesis",
    ]
    assert events[1]["data"] == {"source_kinds": ["knowledge", "web"]}
    report_path = store.report_path(user, conversation.id)
    assert report_path is not None
    # G3 起报告路径存相对路径（相对报告根目录）
    assert (tmp_path / "reports" / report_path).exists()


@pytest.mark.asyncio
async def test_application_marks_safe_failure_and_does_not_publish_report(
    tmp_path: Path,
) -> None:
    class FailingEngine:
        async def run(self, turn, *, user_knowledge=None, emit=None):
            raise RuntimeError("provider details must not leak")

    store = ConversationStore(tmp_path / "reasonix.sqlite3")
    user = store.authenticate("user", "0000")
    assert user is not None
    conversation = store.create_conversation(user, "失败研究")
    application = ConversationApplication(
        store,
        FailingEngine(),
        ConversationReport(tmp_path / "reports", store),
    )
    turn = await application.submit(
        user, conversation.id, question="问题", use_web=False
    )

    events = []
    await application.execute(user, conversation.id, turn.id, emit=events.append)

    assert store.get_turn(user, conversation.id, turn.id).status == "failed"
    assert events[-1]["type"] == "turn.failed"
    assert "provider details" not in events[-1]["message"]



@pytest.mark.asyncio
async def test_application_bounds_recent_history_before_model_input(
    tmp_path: Path,
) -> None:
    store = ConversationStore(tmp_path / "reasonix.sqlite3")
    user = store.authenticate("user", "0000")
    assert user is not None
    conversation = store.create_conversation(user, "上下文预算")
    engine = Engine([])
    application = ConversationApplication(
        store,
        engine,
        ConversationReport(tmp_path / "reports", store),
    )
    for index in range(7):
        turn = await application.submit(
            user, conversation.id, question=f"历史问题 {index}", use_web=False
        )
        await application.execute(user, conversation.id, turn.id)
        engine.seen.clear()
        # Simulate long prior answers without exposing historical evidence.
        with store._connect() as connection:
            connection.execute(
                "UPDATE turns SET answer = ? WHERE id = ?",
                (str(index) * 5000, turn.id),
            )
    current = await application.submit(
        user, conversation.id, question="当前问题", use_web=False
    )

    await application.execute(user, conversation.id, current.id)

    history = engine.seen[-1].recent_history
    assert len(history) <= 6
    assert sum(len(question) + len(answer) for question, answer in history) <= 12000
    assert all("历史问题 0" != question for question, _ in history)


@pytest.mark.asyncio
async def test_application_does_not_emit_a_second_terminal_event(
    tmp_path: Path,
) -> None:
    store = ConversationStore(tmp_path / "reasonix.sqlite3")
    user = store.authenticate("user", "0000")
    assert user is not None
    conversation = store.create_conversation(user, "终态幂等")
    application = ConversationApplication(
        store,
        Engine([]),
        ConversationReport(tmp_path / "reports", store),
    )
    turn = await application.submit(
        user, conversation.id, question="问题", use_web=False
    )
    first_events = []
    await application.execute(user, conversation.id, turn.id, emit=first_events.append)
    second_events = []
    await application.execute(user, conversation.id, turn.id, emit=second_events.append)

    assert first_events[-1]["type"] == "turn.completed"
    assert second_events == []


@pytest.mark.asyncio
async def test_first_successful_turn_assigns_an_automatic_title(tmp_path: Path) -> None:
    store = ConversationStore(tmp_path / "reasonix.sqlite3")
    user = store.authenticate("user", "0000")
    assert user is not None
    conversation = store.create_conversation(user)
    application = ConversationApplication(
        store,
        Engine([]),
        ConversationReport(tmp_path / "reports", store),
    )
    turn = await application.submit(
        user,
        conversation.id,
        question="我想了解 LangGraph 的状态和持久化应该怎么入门？",
        use_web=False,
    )

    await application.execute(user, conversation.id, turn.id)

    assert store.get_conversation(user, conversation.id).title == (
        "LangGraph 的状态和持久化应该怎么入门"
    )


@pytest.mark.asyncio
async def test_turn_lock_entry_is_reclaimed_after_execution(tmp_path: Path) -> None:
    import gc

    store = ConversationStore(tmp_path / "reasonix.sqlite3")
    user = store.authenticate("user", "0000")
    assert user is not None
    conversation = store.create_conversation(user, "锁回收")
    application = ConversationApplication(
        store, Engine([]), ConversationReport(tmp_path / "reports", store)
    )
    turn = await application.submit(
        user, conversation.id, question="问题", use_web=False
    )
    await application.execute(user, conversation.id, turn.id)
    del turn
    gc.collect()
    # 弱值字典：回合结束后锁条目自动回收，不随进程生命周期累积（G3）
    assert len(application._turn_locks) == 0


@pytest.mark.asyncio
async def test_submit_reclaims_stale_running_turns_first(tmp_path: Path) -> None:
    store = ConversationStore(tmp_path / "reasonix.sqlite3")
    user = store.authenticate("user", "0000")
    assert user is not None
    conversation = store.create_conversation(user, "僵尸回收")
    orphan = store.start_turn(user, conversation.id, question="遗留", use_web=False)
    application = ConversationApplication(
        store,
        Engine([]),
        ConversationReport(tmp_path / "reports", store),
        stale_turn_seconds=0,
    )
    await application.submit(user, conversation.id, question="新一问", use_web=False)
    assert store.get_turn(user, conversation.id, orphan.id).status == "failed"


@pytest.mark.asyncio
async def test_turn_failure_carries_model_error_category(tmp_path: Path) -> None:
    from app.conversation.turn import TurnExecutionError

    class TimeoutEngine:
        async def run(self, turn, *, user_knowledge=None, emit=None):
            raise TurnExecutionError("model-timeout")

    store = ConversationStore(tmp_path / "reasonix.sqlite3")
    user = store.authenticate("user", "0000")
    assert user is not None
    conversation = store.create_conversation(user, "错误分类")
    application = ConversationApplication(
        store, TimeoutEngine(), ConversationReport(tmp_path / "reports", store)
    )
    turn = await application.submit(
        user, conversation.id, question="问题", use_web=False
    )
    events: list[dict[str, object]] = []
    failed = await application.execute(
        user, conversation.id, turn.id, emit=events.append
    )

    assert failed.status == "failed"
    assert failed.result is not None
    assert failed.result["error"] == "研究模型请求超时，请稍后重试"
    failed_events = [e for e in events if e["type"] == "turn.failed"]
    assert failed_events
    assert failed_events[0]["data"].get("error_kind") == "model-timeout"


@pytest.mark.asyncio
async def test_unclassified_failure_keeps_legacy_message_and_event_shape(
    tmp_path: Path,
) -> None:
    class BrokenEngine:
        async def run(self, turn, *, user_knowledge=None, emit=None):
            raise RuntimeError("boom")

    store = ConversationStore(tmp_path / "reasonix.sqlite3")
    user = store.authenticate("user", "0000")
    assert user is not None
    conversation = store.create_conversation(user, "未知错误")
    application = ConversationApplication(
        store, BrokenEngine(), ConversationReport(tmp_path / "reports", store)
    )
    turn = await application.submit(
        user, conversation.id, question="问题", use_web=False
    )
    events: list[dict[str, object]] = []
    failed = await application.execute(
        user, conversation.id, turn.id, emit=events.append
    )

    assert failed.status == "failed"
    assert failed.result is not None
    assert failed.result["error"] == "本轮研究未能完成，请稍后重试。"
    failed_events = [e for e in events if e["type"] == "turn.failed"]
    assert failed_events and "error_kind" not in failed_events[0]["data"]


def test_truncate_at_sentence_keeps_complete_sentences() -> None:
    from app.conversation.application import _truncate_at_sentence

    text = "第一句结论。" + "细节" * 200 + "结尾句。"
    truncated = _truncate_at_sentence(text, 50)
    assert truncated == "第一句结论。"
    assert len(_truncate_at_sentence(text, 10)) <= 10
    # 无任何句末标点时退化为字符截断，预算上限依然成立
    no_punct = "字" * 300
    assert len(_truncate_at_sentence(no_punct, 100)) == 100
    # 短文本原样保留
    assert _truncate_at_sentence("完整回答。", 100) == "完整回答。"


@pytest.mark.asyncio
async def test_turn_limit_rejects_when_configured(tmp_path: Path) -> None:
    store = ConversationStore(tmp_path / "reasonix.sqlite3")
    user = store.authenticate("user", "0000")
    assert user is not None
    conversation = store.create_conversation(user, "轮次上限")
    application = ConversationApplication(
        store,
        Engine([]),
        ConversationReport(tmp_path / "reports", store),
        max_turns_per_conversation=1,
    )
    first = await application.submit(
        user, conversation.id, question="第一问", use_web=False
    )
    with pytest.raises(ValueError, match="turn limit"):
        await application.submit(
            user, conversation.id, question="第二问", use_web=False
        )
    assert first.status == "running"


@pytest.mark.asyncio
async def test_model_title_generation_wins_and_falls_back_to_regex(
    tmp_path: Path,
) -> None:
    class TitleGenerator:
        def __init__(self, fail: bool = False):
            self.fail = fail
            self.asked: list[str] = []

        async def generate(self, question: str) -> str:
            self.asked.append(question)
            if self.fail:
                raise RuntimeError("title model down")
            return "LangGraph 状态图入门"

    store = ConversationStore(tmp_path / "reasonix.sqlite3")
    user = store.authenticate("user", "0000")
    assert user is not None

    success = TitleGenerator()
    conversation = store.create_conversation(user, "新研究")
    application = ConversationApplication(
        store, Engine([]), ConversationReport(tmp_path / "reports", store),
        title_generator=success,
    )
    turn = await application.submit(user, conversation.id, question="请问什么是 LangGraph？", use_web=False)
    await application.execute(user, conversation.id, turn.id)
    assert store.get_conversation(user, conversation.id).title == "LangGraph 状态图入门"

    # 模型失败 → 回退正则剥前缀路径
    fallback = TitleGenerator(fail=True)
    second = store.create_conversation(user, "新研究")
    application2 = ConversationApplication(
        store, Engine([]), ConversationReport(tmp_path / "reports", store),
        title_generator=fallback,
    )
    turn2 = await application2.submit(user, second.id, question="我想了解向量数据库", use_web=False)
    await application2.execute(user, second.id, turn2.id)
    assert store.get_conversation(user, second.id).title == "向量数据库"

    # 用户已手动命名 → 模型标题不覆盖
    third = store.create_conversation(user, "我的专属标题")
    application3 = ConversationApplication(
        store, Engine([]), ConversationReport(tmp_path / "reports", store),
        title_generator=TitleGenerator(),
    )
    turn3 = await application3.submit(user, third.id, question="随便问问", use_web=False)
    await application3.execute(user, third.id, turn3.id)
    assert store.get_conversation(user, third.id).title == "我的专属标题"
