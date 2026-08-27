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

    async def run(self, turn, *, user_knowledge=None):
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
    assert report_path is not None and Path(report_path).exists()


@pytest.mark.asyncio
async def test_application_marks_safe_failure_and_does_not_publish_report(
    tmp_path: Path,
) -> None:
    class FailingEngine:
        async def run(self, turn, *, user_knowledge=None):
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
