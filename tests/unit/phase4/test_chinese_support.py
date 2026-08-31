"""I6 敌意套件（RED-first）：中文 claim/quote 的词法支撑判定。

中文路径（app.citations.chinese）是 rules.py 的并行输入处理层——
判定语义（r1 精确包含 / r2 重叠阈值 / r6 否定冲突 / 数字锚点）镜像
原规则但适配中文；rules.py 原函数零改动（红线4）。
"""

from __future__ import annotations

import pytest

from app.citations.chinese import (
    Verdict,
    check_chinese,
    tokenize_chinese,
)


def claim(statement: str) -> dict[str, object]:
    return {"claim_id": "claim-1", "statement": statement}


def evidence(quote: str, *, source_kind: str = "knowledge") -> dict[str, object]:
    return {
        "evidence_id": "ev-1",
        "source_id": "knowledge-evaluation-notes-v1",
        "source_kind": source_kind,
        "content_sha256": "0" * 64,
        "locator": {"kind": "section", "value": "doc#1"},
        "quote": quote,
    }


def test_tokenizer_keeps_english_words_and_chinese_bigrams() -> None:
    tokens = tokenize_chinese("每日预算200万")
    assert "200" in tokens
    assert "每日" in tokens
    assert "预算" in tokens
    assert "万" in tokens  # 单字也保留（数字量级词）


def test_chinese_exact_containment_is_supported() -> None:
    judgment = check_chinese(
        claim("个人每日 token 预算为 200 万"),
        evidence("每人每日 token 预算为 200 万；超过 150 万自动提醒。"),
    )
    assert judgment.verdict is Verdict.SUPPORTED


def test_chinese_partial_overlap_meeting_threshold_is_supported() -> None:
    judgment = check_chinese(
        claim("单次任务超过 80 万 token 需要提前报备"),
        evidence(
            "单次任务预计消耗超过 80 万 token 的，需要提前在运维群报备；"
            "每人每日 token 预算为 200 万。"
        ),
    )
    assert judgment.verdict is Verdict.SUPPORTED


def test_chinese_digit_mismatch_is_unsupported() -> None:
    judgment = check_chinese(
        claim("个人每日 token 预算为 500 万"),
        evidence("每人每日 token 预算为 200 万；超过 150 万自动提醒。"),
    )
    assert judgment.verdict is Verdict.UNSUPPORTED


def test_chinese_negation_conflict_is_contradicted() -> None:
    judgment = check_chinese(
        claim("客户数据可以进入模型输入"),
        evidence("客户数据、生产库凭据、密钥文件严禁进入任何模型输入。"),
    )
    assert judgment.verdict is Verdict.CONTRADICTED


def test_chinese_negation_in_claim_does_not_conflict() -> None:
    judgment = check_chinese(
        claim("客户数据严禁进入任何模型输入"),
        evidence("客户数据、生产库凭据、密钥文件严禁进入任何模型输入。"),
    )
    assert judgment.verdict is Verdict.SUPPORTED


def test_chinese_low_overlap_without_digits_is_unsupported() -> None:
    judgment = check_chinese(
        claim("违规会被立即开除"),
        evidence("首次违规暂停账号 3 天并复盘；累计两次升级至部门负责人处理。"),
    )
    assert judgment.verdict is Verdict.UNSUPPORTED


def test_english_claims_still_judged_under_chinese_path() -> None:
    judgment = check_chinese(
        claim("The daily budget is 2000000 tokens"),
        evidence("each person has a daily budget of 2000000 tokens per day"),
    )
    assert judgment.verdict is Verdict.SUPPORTED


def test_empty_claim_is_unsupported() -> None:
    judgment = check_chinese(claim("   "), evidence("有效证据内容。"))
    assert judgment.verdict is Verdict.UNSUPPORTED


@pytest.mark.parametrize(
    ("verdict_a", "verdict_b"),
    [
        (Verdict.SUPPORTED, Verdict.UNSUPPORTED),
        (Verdict.CONTRADICTED, Verdict.SUPPORTED),
    ],
)
def test_verdicts_are_distinct(verdict_a: Verdict, verdict_b: Verdict) -> None:
    assert verdict_a is not verdict_b


def test_adapter_routes_to_chinese_path_only_when_both_flags_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.citations import runtime_adapter
    from app.conversation.contracts import Claim as ConvClaim
    from app.conversation.contracts import EvidenceItem as ConvEvidence

    # 纯中文、无英文 token 的改写声明：英文引擎提取不到 token → 误杀
    conv_claim = ConvClaim(
        "claim-1", "月度团队预算超出部分要走下季度追加审批流程", ("ev-1",)
    )
    conv_evidence = ConvEvidence(
        "ev-1",
        "knowledge",
        "政策",
        "chunk",
        "policy#1",
        "月度团队预算上限 6000 万 token，超出部分走下季度追加审批流程。",
    )

    monkeypatch.setenv("ENABLE_CITATION_VALIDATION", "1")
    monkeypatch.delenv("CITATIONS_CHINESE_TOKENIZER", raising=False)
    reports = runtime_adapter.validate_claims((conv_claim,), (conv_evidence,))
    # 英文引擎对纯中文改写失效 → 误判 unsupported（基线行为）
    assert reports[0].supported is False

    monkeypatch.setenv("CITATIONS_CHINESE_TOKENIZER", "1")
    reports = runtime_adapter.validate_claims((conv_claim,), (conv_evidence,))
    # 中文路径 → 正确判定 supported
    assert reports[0].supported is True


def test_chinese_flag_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.citations.chinese import chinese_enabled

    monkeypatch.delenv("CITATIONS_CHINESE_TOKENIZER", raising=False)
    assert chinese_enabled({}) is False
    assert chinese_enabled({"CITATIONS_CHINESE_TOKENIZER": "1"}) is True


def test_all_branch_reasons_are_tuple_of_str() -> None:
    """I6 回归：reasons 缺尾逗号会变成 str，adapter 迭代时逐字符展开
    （真机 ": t" 根因）。锁定所有分支的 reasons 必须是 tuple[str, ...]。"""
    cases = [
        (
            claim("个人每日 token 预算为 200 万"),
            evidence("每人每日 token 预算为 200 万。"),
        ),
        (
            claim("个人每日 token 预算为 500 万"),
            evidence("每人每日 token 预算为 200 万。"),
        ),
        (
            claim("客户数据可以进入模型输入"),
            evidence("客户数据严禁进入任何模型输入。"),
        ),
        (
            claim("违规会被立即开除"),
            evidence("首次违规暂停账号 3 天并复盘。"),
        ),
        (claim("   "), evidence("有效证据内容。")),
    ]
    for claim_input, evidence_input in cases:
        judgment = check_chinese(claim_input, evidence_input)
        assert isinstance(judgment.reasons, tuple), judgment
        assert all(isinstance(item, str) for item in judgment.reasons)
        if judgment.reasons:
            assert len(judgment.reasons[0]) > 1  # 不再是单字符


def test_digit_anchor_normalizes_leading_zeros() -> None:
    judgment = check_chinese(
        claim("设备编号 DEV-023 在用"), evidence("编号 DEV-23 的设备状态在用")
    )
    assert judgment.verdict is Verdict.SUPPORTED
