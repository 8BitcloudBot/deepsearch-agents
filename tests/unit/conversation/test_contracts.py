import pytest

from app.conversation.contracts import (
    Claim,
    EvidenceItem,
    TurnResearchPlan,
    TurnResult,
)


def test_schema_5_turn_result_rejects_claims_with_unknown_evidence() -> None:
    evidence = EvidenceItem(
        evidence_id="ev-knowledge-1",
        source_kind="knowledge",
        title="LangGraph persistence",
        locator_kind="chunk",
        locator_value="langgraph.md#persistence",
        quote="A checkpointer persists graph state between turns.",
    )

    with pytest.raises(ValueError, match="unknown evidence"):
        TurnResult(
            schema_version="5.0.0",
            answer="可以使用检查点保存会话状态。[1]",
            claims=(
                Claim(
                    claim_id="claim-1",
                    statement="检查点用于保存会话状态。",
                    evidence_ids=("ev-missing",),
                ),
            ),
            evidence=(evidence,),
            limitations=(),
        )


def test_turn_research_plan_enforces_bounded_queries() -> None:
    with pytest.raises(ValueError, match="web queries"):
        TurnResearchPlan(
            objective="比较三个方案",
            subquestions=("问题一",),
            knowledge_queries=("知识库查询",),
            web_queries=("查询一", "查询二", "查询三", "查询四"),
        )


def test_turn_result_round_trips_through_public_schema() -> None:
    result = TurnResult(
        schema_version="5.0.0",
        answer="中文回答。[1]",
        claims=(Claim("claim-1", "声明", ("ev-web-1",)),),
        evidence=(
            EvidenceItem(
                evidence_id="ev-web-1",
                source_kind="web",
                title="Source title",
                locator_kind="url",
                locator_value="https://example.com/doc",
                quote="Original evidence quote.",
                hostname="example.com",
            ),
        ),
        limitations=("存在限制。",),
    )

    assert TurnResult.from_dict(result.as_dict()) == result
