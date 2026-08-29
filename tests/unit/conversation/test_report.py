from pathlib import Path

from app.conversation.contracts import Claim, EvidenceItem, TurnResult
from app.conversation.report import ConversationReport
from app.conversation.store import ConversationStore


def result(answer: str, evidence_id: str, url: str) -> TurnResult:
    return TurnResult(
        schema_version="5.0.0",
        answer=answer,
        claims=(Claim("claim-1", "LangGraph 可以保存对话状态。", (evidence_id,)),),
        evidence=(
            EvidenceItem(
                evidence_id=evidence_id,
                source_kind="web",
                title="LangGraph documentation",
                locator_kind="url",
                locator_value=url,
                quote="Checkpointers persist graph state across interactions.",
                hostname="docs.langchain.com",
                published_at="2026-08-01",
            ),
            EvidenceItem(
                evidence_id=f"{evidence_id}-unused",
                source_kind="web",
                title="Unused search result",
                locator_kind="url",
                locator_value="https://unused.example/raw",
                quote="This candidate was not cited.",
            ),
        ),
        limitations=("未覆盖部署规模问题。",),
    )


def test_report_accumulates_completed_turns_and_only_cited_evidence(
    tmp_path: Path,
) -> None:
    repository = ConversationStore(tmp_path / "reasonix.sqlite3")
    user = repository.authenticate("user", "0000")
    assert user is not None
    conversation = repository.create_conversation(user, "AI 助手入门")
    first = repository.start_turn(
        user, conversation.id, question="什么是状态？", use_web=True
    )
    repository.complete_turn(
        user,
        conversation.id,
        first.id,
        result("第一轮回答。[1]", "ev-web-1", "https://docs.langchain.com/state"),
    )
    second = repository.start_turn(
        user, conversation.id, question="如何保存？", use_web=True
    )
    repository.complete_turn(
        user,
        conversation.id,
        second.id,
        result("第二轮回答。[1]", "ev-web-2", "https://docs.langchain.com/state"),
    )

    report = ConversationReport(tmp_path / "reports", repository)
    path = report.refresh(user, conversation.id)
    markdown = path.read_text(encoding="utf-8")

    assert "# AI 助手入门" in markdown
    assert "- 更新时间：" in markdown
    assert "## 第 1 轮：什么是状态？" in markdown
    assert "## 第 2 轮：如何保存？" in markdown
    assert "### 结论依据" in markdown
    assert "Checkpointers persist graph state" in markdown
    assert "### 本轮限制" in markdown
    assert markdown.index("### 本轮限制") < markdown.index("### 回答")
    assert "### 本轮证据" not in markdown
    assert "补充检索来源" not in markdown
    assert "Unused search result" not in markdown
    assert "docs.langchain.com" in markdown
    assert "引用回合：1、2" in markdown
    assert markdown.count("## 证据附录（累计来源索引）") == 1
    assert markdown.count("Checkpointers persist graph state") == 1


def test_ten_turn_report_has_one_deduplicated_evidence_appendix(
    tmp_path: Path,
) -> None:
    repository = ConversationStore(tmp_path / "reasonix.sqlite3")
    user = repository.authenticate("user", "0000")
    assert user is not None
    conversation = repository.create_conversation(user, "十轮研究")
    for index in range(1, 11):
        turn = repository.start_turn(
            user,
            conversation.id,
            question=f"第 {index} 个问题",
            use_web=True,
        )
        repository.complete_turn(
            user,
            conversation.id,
            turn.id,
            result(
                ("这是精简回答。" * 40) + "[1]",
                f"ev-web-{index}",
                "https://docs.langchain.com/state",
            ),
        )

    markdown = ConversationReport(tmp_path / "reports", repository).refresh(
        user, conversation.id
    ).read_text(encoding="utf-8")

    assert markdown.count("## 证据附录（累计来源索引）") == 1
    assert markdown.count("Checkpointers persist graph state") == 1
    assert "引用回合：1、2、3、4、5、6、7、8、9、10" in markdown
    assert "Unused search result" not in markdown
    assert len(markdown.encode("utf-8")) <= 45 * 1024


def test_report_ignores_running_and_failed_turns(tmp_path: Path) -> None:
    repository = ConversationStore(tmp_path / "reasonix.sqlite3")
    user = repository.authenticate("user", "0000")
    assert user is not None
    conversation = repository.create_conversation(user, "失败隔离")
    repository.start_turn(user, conversation.id, question="运行中问题", use_web=False)

    report = ConversationReport(tmp_path / "reports", repository)
    markdown = report.refresh(user, conversation.id).read_text(encoding="utf-8")

    assert "运行中问题" not in markdown
    assert "当前尚无已完成的研究回合。" in markdown


def test_refresh_records_relative_path_and_discard_removes_directory(
    tmp_path: Path,
) -> None:
    repository = ConversationStore(tmp_path / "reasonix.sqlite3")
    user = repository.authenticate("user", "0000")
    assert user is not None
    conversation = repository.create_conversation(user, "清理测试")
    turn = repository.start_turn(
        user, conversation.id, question="什么是状态？", use_web=True
    )
    repository.complete_turn(
        user,
        conversation.id,
        turn.id,
        result("回答。[1]", "ev-web-1", "https://docs.langchain.com/state"),
    )
    report = ConversationReport(tmp_path / "reports", repository)
    report.refresh(user, conversation.id)

    stored = repository.report_path(user, conversation.id)
    assert stored is not None and not stored.startswith("/")

    report.discard(user, conversation.id)
    assert not (tmp_path / "reports" / conversation.id).exists()

    repository.delete_conversation(user, conversation.id)
    import pytest as _pytest

    with _pytest.raises(LookupError):
        report.discard(user, conversation.id)
