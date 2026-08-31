import asyncio
from dataclasses import dataclass

import pytest

from app.conversation.contracts import EvidenceItem, TurnResearchPlan
from app.conversation.settings import ConversationSettings
from app.conversation.turn import (
    _MAX_SUPPLEMENTAL_QUERIES_TOTAL,
    _MAX_SUPPLEMENTAL_ROUNDS,
    CoverageDecision,
    SynthesisClaim,
    SynthesisDraft,
    SynthesisSection,
    TurnExecutionError,
    TurnInput,
    TurnResearchEngine,
)


def evidence(kind: str, number: int, host: str | None = None) -> EvidenceItem:
    locator_kind = (
        "url" if kind == "web" else "file" if kind == "session_file" else "chunk"
    )
    locator_value = (
        f"https://{host}/article-{number}"
        if kind == "web"
        else f"document-{number}.md#section"
    )
    return EvidenceItem(
        evidence_id=f"ev-{kind}-{number}",
        source_kind=kind,
        title=f"{kind} source {number}",
        locator_kind=locator_kind,
        locator_value=locator_value,
        quote=f"Evidence quote {kind} {number}",
        hostname=host,
    )


class Planner:
    async def plan(self, turn: TurnInput) -> TurnResearchPlan:
        return TurnResearchPlan(
            objective=turn.question,
            subquestions=(turn.question,),
            knowledge_queries=("knowledge query",),
            web_queries=("web query",) if turn.use_web else (),
        )


class Retriever:
    def __init__(self, results: tuple[EvidenceItem, ...]):
        self.results = results
        self.calls: list[object] = []

    async def search(self, query: str, *, limit: int = 10) -> tuple[EvidenceItem, ...]:
        self.calls.append(query)
        return self.results[:limit]


def build_engine(
    planner,
    knowledge,
    _files=None,
    web=None,
    synthesizer=None,
    coverage_reviewer=None,
    **kwargs,
):
    """T1 后引擎不再有 session_file 检索器参数；垫片保持既有测试可读，
    会话文件维度已由知识库入库方案取代，恒为空。"""
    _ = _files
    return TurnResearchEngine(
        planner, knowledge, web, synthesizer, coverage_reviewer, **kwargs
    )


class FileRetriever:
    def __init__(self, results: tuple[EvidenceItem, ...]):
        self.results = results
        self.calls: list[tuple[tuple[str, ...], str]] = []

    async def search(
        self,
        attachment_ids: tuple[str, ...],
        query: str,
        *,
        limit: int = 10,
    ) -> tuple[EvidenceItem, ...]:
        self.calls.append((attachment_ids, query))
        return self.results[:limit]


@dataclass
class Synthesizer:
    draft: SynthesisDraft
    seen_evidence: tuple[EvidenceItem, ...] = ()

    async def synthesize(
        self,
        turn: TurnInput,
        plan: TurnResearchPlan,
        evidence_items: tuple[EvidenceItem, ...],
        limitations: tuple[str, ...],
    ) -> SynthesisDraft:
        self.seen_evidence = evidence_items
        return self.draft


@pytest.mark.asyncio
async def test_turn_graph_uses_only_enabled_and_available_sources() -> None:
    knowledge = Retriever((evidence("knowledge", 1),))
    files = FileRetriever((evidence("session_file", 1),))
    web = Retriever((evidence("web", 1, "docs.example.com"),))
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("这是回答。", (0,)),),
            claims=(SynthesisClaim("这是有依据的结论。", ("ev-knowledge-1",)),),
            limitations=(),
        )
    )
    engine = build_engine(Planner(), knowledge, files, web, synthesizer)

    result = await engine.run(
        TurnInput(
            question="如何入门？",
            use_web=False,
            attachment_ids=(),
            recent_history=(),
        )
    )

    assert knowledge.calls == ["knowledge query"]
    assert files.calls == []
    assert web.calls == []
    assert result.schema_version == "5.0.0"
    assert result.claims[0].evidence_ids == ("ev-knowledge-1",)


@pytest.mark.asyncio
async def test_turn_graph_uses_web_when_requested() -> None:
    knowledge = Retriever((evidence("knowledge", 1),))
    web = Retriever((evidence("web", 1, "docs.example.com"),))
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("综合回答。", (0,)),),
            claims=(
                SynthesisClaim(
                    "组合证据结论。",
                    ("ev-knowledge-1", "ev-web-1"),
                ),
            ),
            limitations=(),
        )
    )
    engine = build_engine(Planner(), knowledge, None, web, synthesizer)

    await engine.run(
        TurnInput(
            question="结合知识库和网络说明",
            use_web=True,
            attachment_ids=(),
            recent_history=(("上一问", "上一答"),),
        )
    )

    assert web.calls == ["web query"]
    assert {item.source_kind for item in synthesizer.seen_evidence} == {
        "knowledge",
        "web",
    }


@pytest.mark.asyncio
async def test_evidence_delivery_is_bounded_with_per_source_floor() -> None:
    knowledge = Retriever(tuple(evidence("knowledge", index) for index in range(1, 8)))
    web = Retriever(
        tuple(evidence("web", index, f"host{index}.example") for index in range(1, 8))
    )
    claims = tuple(
        SynthesisClaim(f"结论 {index}", (item.evidence_id,))
        for index, item in enumerate(
            (
                evidence("knowledge", 1),
                evidence("web", 1, "host1.example"),
            )
        )
    )
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0, 1)),),
            claims=claims,
            limitations=(),
        )
    )
    engine = build_engine(Planner(), knowledge, None, web, synthesizer)

    await engine.run(
        TurnInput("问题", True, (), ()),
    )

    seen = synthesizer.seen_evidence
    assert len(seen) == 6
    # 每非空来源保底入选（round-robin 已被全局分数序取代；
    # session_file 维度已由知识库入库方案取代，恒为空）
    kinds = {item.source_kind for item in seen}
    assert {"knowledge", "web"} <= kinds
    # web 批次获得引擎统一重编的衰减分，输出按分数降序
    web_scores = [item.score for item in seen if item.source_kind == "web"]
    assert web_scores == sorted(web_scores, reverse=True)
    assert web_scores[0] == max(web_scores)
    assert seen[0].evidence_id == "ev-web-1"


@pytest.mark.asyncio
async def test_unknown_evidence_only_removes_its_claim_and_section() -> None:
    knowledge = Retriever((evidence("knowledge", 1),))
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(
                SynthesisSection("保留段落。", (0,)),
                SynthesisSection("删除段落。", (1,)),
            ),
            claims=(
                SynthesisClaim("有效声明。", ("ev-knowledge-1",)),
                SynthesisClaim("无效声明。", ("ev-unknown",)),
            ),
            limitations=(),
        )
    )
    engine = build_engine(
        Planner(), knowledge, FileRetriever(()), Retriever(()), synthesizer
    )

    result = await engine.run(TurnInput("问题", False, (), ()))

    assert result.answer.startswith("保留段落。")
    assert "删除段落" not in result.answer
    assert [claim.statement for claim in result.claims] == ["有效声明。"]


@pytest.mark.asyncio
async def test_external_evidence_with_zero_valid_claims_degrades_to_snapshot() -> None:
    """B10-3 后引用幻觉（claims 全无效）同样降级为证据快照而非整轮失败。"""
    knowledge = Retriever((evidence("knowledge", 1),))
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("无引用回答。", (0,)),),
            claims=(SynthesisClaim("无效声明。", ("ev-unknown",)),),
            limitations=(),
        )
    )
    engine = build_engine(
        Planner(), knowledge, FileRetriever(()), Retriever(()), synthesizer
    )

    result = await engine.run(TurnInput("问题", False, (), ()))
    assert result.answer.startswith("模型综合服务本轮未能完成整理")
    assert result.claims == ()
    assert "knowledge source 1" in result.answer


@pytest.mark.asyncio
async def test_invalid_external_synthesis_is_retried_once_before_failure() -> None:
    class RetryingSynthesizer(Synthesizer):
        calls = 0

        async def synthesize(self, turn, plan, evidence_items, limitations):
            self.calls += 1
            if self.calls == 1:
                return SynthesisDraft(
                    sections=(SynthesisSection("无效回答。", (0,)),),
                    claims=(SynthesisClaim("无效声明。", ("ev-missing",)),),
                    limitations=(),
                )
            return SynthesisDraft(
                sections=(SynthesisSection("有效回答。", (0,)),),
                claims=(SynthesisClaim("有效声明。", ("ev-knowledge-1",)),),
                limitations=(),
            )

    synthesizer = RetryingSynthesizer(SynthesisDraft((), (), ()))
    engine = build_engine(
        Planner(),
        Retriever((evidence("knowledge", 1),)),
        FileRetriever(()),
        Retriever(()),
        synthesizer,
    )

    result = await engine.run(TurnInput("问题", False, (), ()))

    assert synthesizer.calls == 2
    assert result.claims[0].statement == "有效声明。"


@pytest.mark.asyncio
async def test_bounded_coverage_review_runs_only_new_supplemental_queries() -> None:
    knowledge = Retriever((evidence("knowledge", 1),))
    knowledge.results = (evidence("knowledge", 1), evidence("knowledge", 2))
    web = Retriever((evidence("web", 1, "docs.example.com"),))

    class Reviewer:
        async def review(self, turn, plan, evidence_items, limitations):
            return CoverageDecision(
                uncovered_questions=("补充问题",),
                knowledge_queries=("new query", "knowledge query"),
                web_queries=(),
            )

    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("补充后的回答。", (0,)),),
            claims=(SynthesisClaim("补充结论。", ("ev-knowledge-1",)),),
            limitations=(),
        )
    )
    engine = build_engine(
        Planner(), knowledge, FileRetriever(()), web, synthesizer, Reviewer()
    )

    result = await engine.run(TurnInput("问题", False, (), ()))

    assert knowledge.calls == ["knowledge query", "new query"]
    assert result.claims[0].evidence_ids == ("ev-knowledge-1",)


@pytest.mark.asyncio
async def test_coverage_does_not_repeat_question_fallback_when_plan_has_no_queries():
    knowledge = Retriever((evidence("knowledge", 1),))

    class EmptyPlanner:
        async def plan(self, turn: TurnInput) -> TurnResearchPlan:
            return TurnResearchPlan(
                objective=turn.question,
                subquestions=(),
                knowledge_queries=(),
                web_queries=(),
            )

    class Reviewer:
        async def review(self, turn, plan, evidence_items, limitations):
            return CoverageDecision(
                uncovered_questions=("补充问题",),
                knowledge_queries=(turn.question,),
            )

    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0,)),),
            claims=(SynthesisClaim("结论。", ("ev-knowledge-1",)),),
            limitations=(),
        )
    )
    engine = build_engine(
        EmptyPlanner(),
        knowledge,
        FileRetriever(()),
        Retriever(()),
        synthesizer,
        Reviewer(),
    )

    await engine.run(TurnInput("问题", False, (), ()))

    assert knowledge.calls == ["问题"]


@pytest.mark.asyncio
async def test_enabled_sources_begin_retrieval_concurrently() -> None:
    started: set[str] = set()
    all_started = asyncio.Event()

    class BlockingRetriever(Retriever):
        def __init__(self, name: str, results: tuple[EvidenceItem, ...]):
            super().__init__(results)
            self.name = name

        async def search(self, query: str, *, limit: int = 10):
            self.calls.append(query)
            started.add(self.name)
            if len(started) == 2:
                all_started.set()
            await asyncio.wait_for(all_started.wait(), timeout=0.2)
            return self.results[:limit]

    knowledge = BlockingRetriever("knowledge", (evidence("knowledge", 1),))
    web = BlockingRetriever("web", (evidence("web", 1, "docs.example.com"),))
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0,)),),
            claims=(SynthesisClaim("结论。", ("ev-knowledge-1",)),),
            limitations=(),
        )
    )

    await build_engine(Planner(), knowledge, None, web, synthesizer).run(
        TurnInput("问题", True, (), ())
    )

    assert started == {"knowledge", "web"}


@pytest.mark.asyncio
async def test_standard_mode_bounds_web_queries_and_evidence() -> None:
    class ManyQueryPlanner:
        async def plan(self, turn: TurnInput) -> TurnResearchPlan:
            return TurnResearchPlan(
                objective=turn.question,
                subquestions=("一", "二", "三"),
                knowledge_queries=("knowledge one", "knowledge two"),
                web_queries=("web one", "web two", "web three"),
            )

    knowledge = Retriever(tuple(evidence("knowledge", index) for index in range(1, 5)))
    web = Retriever(
        tuple(evidence("web", index, f"host{index}.example") for index in range(1, 5))
    )
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0,)),),
            claims=(SynthesisClaim("结论。", ("ev-knowledge-1",)),),
            limitations=(),
        )
    )

    await build_engine(
        ManyQueryPlanner(), knowledge, FileRetriever(()), web, synthesizer
    ).run(TurnInput("普通问题", True, (), ()))

    assert web.calls == ["web one", "web two"]
    assert len(synthesizer.seen_evidence) == 6


@pytest.mark.asyncio
async def test_deep_mode_allows_three_web_queries_and_eight_evidence() -> None:
    class ManyQueryPlanner:
        async def plan(self, turn: TurnInput) -> TurnResearchPlan:
            return TurnResearchPlan(
                objective=turn.question,
                subquestions=("一", "二", "三"),
                knowledge_queries=("knowledge one", "knowledge two"),
                web_queries=("web one", "web two", "web three"),
            )

    knowledge = Retriever(tuple(evidence("knowledge", index) for index in range(1, 6)))
    web = Retriever(
        tuple(evidence("web", index, f"host{index}.example") for index in range(1, 6))
    )
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0,)),),
            claims=(SynthesisClaim("结论。", ("ev-knowledge-1",)),),
            limitations=(),
        )
    )

    await build_engine(
        ManyQueryPlanner(), knowledge, FileRetriever(()), web, synthesizer
    ).run(TurnInput("请做深入全面分析", True, (), ()))

    assert web.calls == ["web one", "web two", "web three"]
    assert len(synthesizer.seen_evidence) == 8


@pytest.mark.asyncio
async def test_complete_initial_coverage_still_reviews_once() -> None:
    class Reviewer:
        calls = 0

        async def review(self, turn, plan, evidence_items, limitations):
            self.calls += 1
            return CoverageDecision()

    reviewer = Reviewer()
    knowledge = Retriever(tuple(evidence("knowledge", index) for index in range(1, 3)))
    web = Retriever(
        tuple(evidence("web", index, f"host{index}.example") for index in range(1, 3))
    )
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0,)),),
            claims=(SynthesisClaim("结论。", ("ev-knowledge-1",)),),
            limitations=(),
        )
    )

    await build_engine(
        Planner(), knowledge, FileRetriever(()), web, synthesizer, reviewer
    ).run(TurnInput("问题", True, (), ()))

    # B8：命中数≠真答了问题，审阅不再被跳过；审阅器返回空 → 直接 synthesize
    assert reviewer.calls == 1


@pytest.mark.asyncio
async def test_pseudo_coverage_with_many_irrelevant_hits_still_reviews() -> None:
    """伪覆盖场景：证据虽多但与子问题无关时，不得跳过审阅。"""
    irrelevant = tuple(evidence("knowledge", index) for index in range(1, 6))

    class Reviewer:
        seen_evidence: tuple[EvidenceItem, ...] = ()

        async def review(self, turn, plan, evidence_items, limitations):
            Reviewer.seen_evidence = evidence_items
            return CoverageDecision(
                uncovered_questions=("未被触及的子问题",),
                knowledge_queries=("真正相关的查询",),
                web_queries=(),
            )

    reviewer = Reviewer()
    knowledge = Retriever(irrelevant)
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0,)),),
            claims=(SynthesisClaim("结论。", ("ev-knowledge-1",)),),
            limitations=(),
        )
    )

    result = await build_engine(
        Planner(), knowledge, FileRetriever(()), Retriever(()), synthesizer, reviewer
    ).run(TurnInput("问题", False, (), ()))

    # 审阅器拿到证据并判定未覆盖，补充查询被执行
    assert len(Reviewer.seen_evidence) >= 4
    assert "真正相关的查询" in knowledge.calls
    assert any("未被触及的子问题" in item for item in result.limitations)


@pytest.mark.asyncio
async def test_sparse_initial_coverage_bounds_supplemental_queries_within_budget():
    class Reviewer:
        calls = 0

        async def review(self, turn, plan, evidence_items, limitations):
            self.calls += 1
            # 每轮重复给出同样的候选：第 1 轮发出每来源第一条（2 条），

    # 第 2 轮从余下候选取新的（又 2 条），第 3 轮全部去重 → 空查询退出
    return CoverageDecision(
        uncovered_questions=("缺口一", "缺口二"),
        knowledge_queries=("knowledge supplement", "knowledge extra"),
        web_queries=("web supplement", "web extra"),
    )

    reviewer = Reviewer()
    knowledge = Retriever((evidence("knowledge", 1),))
    web = Retriever(())
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0,)),),
            claims=(SynthesisClaim("结论。", ("ev-knowledge-1",)),),
            limitations=(),
        )
    )

    await build_engine(
        Planner(), knowledge, FileRetriever(()), web, synthesizer, reviewer
    ).run(TurnInput("问题", True, (), ()))

    assert reviewer.calls == 3
    assert knowledge.calls == [
        "knowledge query",
        "knowledge supplement",
        "knowledge extra",
    ]
    assert web.calls == ["web query", "web supplement", "web extra"]


@pytest.mark.asyncio
async def test_supplemental_loop_runs_multiple_rounds_until_reviewer_converges():
    class Reviewer:
        calls = 0

        async def review(self, turn, plan, evidence_items, limitations):
            self.calls += 1
            done = self.calls >= 3
            return CoverageDecision(
                uncovered_questions=() if done else (f"缺口{self.calls}",),
                knowledge_queries=() if done else (f"followup-{self.calls}",),
                web_queries=(),
            )

    reviewer = Reviewer()
    knowledge = Retriever((evidence("knowledge", 1),))
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0,)),),
            claims=(SynthesisClaim("结论。", ("ev-knowledge-1",)),),
            limitations=(),
        )
    )

    await build_engine(
        Planner(), knowledge, FileRetriever(()), Retriever(()), synthesizer, reviewer
    ).run(TurnInput("问题", False, (), ()))

    # 前两轮各执行 1 条补充查询，第 3 轮审阅收敛为空 → synthesize
    assert knowledge.calls == ["knowledge query", "followup-1", "followup-2"]


@pytest.mark.asyncio
async def test_supplemental_round_budget_exhaustion_records_limitation_without_loop():
    class Reviewer:
        calls = 0

        async def review(self, turn, plan, evidence_items, limitations):
            self.calls += 1
            return CoverageDecision(
                uncovered_questions=("永远缺",),
                knowledge_queries=(f"unique-{self.calls}",),
                web_queries=(f"web-{self.calls}",),
            )

    knowledge = Retriever((evidence("knowledge", 1),))
    web = Retriever((evidence("web", 1, "h.example"),))
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0,)),),
            claims=(SynthesisClaim("结论。", ("ev-knowledge-1",)),),
            limitations=(),
        )
    )

    result = await build_engine(
        Planner(), knowledge, FileRetriever(()), web, synthesizer, Reviewer()
    ).run(TurnInput("问题", True, (), ()))

    issued = len(knowledge.calls) + len(web.calls) - 2
    assert issued == _MAX_SUPPLEMENTAL_QUERIES_TOTAL
    # 每轮两条 × MAX_ROUNDS 轮恰好耗尽预算后退出，不死循环
    assert issued == 2 * _MAX_SUPPLEMENTAL_ROUNDS
    assert any("预算已用尽" in item for item in result.limitations)


@pytest.mark.asyncio
async def test_final_result_prunes_uncited_evidence_and_renumbers_citations() -> None:
    knowledge = Retriever(
        (
            evidence("knowledge", 1),
            evidence("knowledge", 2),
            evidence("knowledge", 3),
        )
    )
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0,)),),
            claims=(SynthesisClaim("结论。", ("ev-knowledge-3",)),),
            limitations=(),
        )
    )

    result = await build_engine(
        Planner(), knowledge, FileRetriever(()), Retriever(()), synthesizer
    ).run(TurnInput("问题", False, (), ()))

    assert [item.evidence_id for item in result.evidence] == ["ev-knowledge-3"]
    assert result.answer == "回答。 [1]"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "maximum"),
    (("普通问题", 1500), ("请深入分析这个问题", 2000)),
)
async def test_quote_limit_follows_answer_depth(question: str, maximum: int) -> None:
    item = EvidenceItem(
        evidence_id="ev-knowledge-long",
        source_kind="knowledge",
        title="长文档",
        locator_kind="chunk",
        locator_value="doc#section",
        quote="证" * 2000,  # 合同层 quote 上限即 2000，深入轮不再额外截断
    )
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0,)),),
            claims=(SynthesisClaim("结论。", (item.evidence_id,)),),
            limitations=(),
        )
    )

    result = await build_engine(
        Planner(), Retriever((item,)), FileRetriever(()), Retriever(()), synthesizer
    ).run(TurnInput(question, False, (), ()))

    assert len(synthesizer.seen_evidence[0].quote) == maximum
    assert len(result.evidence[0].quote) == maximum


@pytest.mark.asyncio
async def test_partial_query_failure_does_not_mark_source_unavailable() -> None:
    class TwoQueryPlanner:
        async def plan(self, turn: TurnInput) -> TurnResearchPlan:
            return TurnResearchPlan(
                objective=turn.question,
                subquestions=(),
                knowledge_queries=("successful", "failed"),
                web_queries=(),
            )

    class PartialRetriever(Retriever):
        async def search(self, query: str, *, limit: int = 10):
            self.calls.append(query)
            if query == "failed":
                raise RuntimeError("provider detail")
            return self.results[:limit]

    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0,)),),
            claims=(SynthesisClaim("结论。", ("ev-knowledge-1",)),),
            limitations=(),
        )
    )
    result = await build_engine(
        TwoQueryPlanner(),
        PartialRetriever((evidence("knowledge", 1),)),
        FileRetriever(()),
        Retriever(()),
        synthesizer,
    ).run(TurnInput("问题", False, (), ()))

    assert "本地知识库部分检索未完成。" in result.limitations
    assert "本地知识库检索暂不可用。" not in result.limitations


@pytest.mark.asyncio
async def test_local_knowledge_queries_are_serialized_but_web_queries_are_concurrent():
    class TwoQueryPlanner:
        async def plan(self, turn: TurnInput) -> TurnResearchPlan:
            return TurnResearchPlan(
                objective=turn.question,
                subquestions=(),
                knowledge_queries=("knowledge one", "knowledge two"),
                web_queries=("web one", "web two"),
            )

    class SingleFlightKnowledge(Retriever):
        active = 0

        async def search(self, query: str, *, limit: int = 10):
            self.calls.append(query)
            self.active += 1
            try:
                if self.active > 1:
                    raise RuntimeError("local index does not support concurrent access")
                await asyncio.sleep(0)
                return self.results[:limit]
            finally:
                self.active -= 1

    web_active = 0
    web_overlap = asyncio.Event()

    class ConcurrentWeb(Retriever):
        async def search(self, query: str, *, limit: int = 10):
            nonlocal web_active
            self.calls.append(query)
            web_active += 1
            if web_active == 2:
                web_overlap.set()
            await asyncio.wait_for(web_overlap.wait(), timeout=0.2)
            web_active -= 1
            return self.results[:limit]

    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0,)),),
            claims=(SynthesisClaim("结论。", ("ev-knowledge-1",)),),
            limitations=(),
        )
    )
    result = await build_engine(
        TwoQueryPlanner(),
        SingleFlightKnowledge((evidence("knowledge", 1),)),
        FileRetriever(()),
        ConcurrentWeb((evidence("web", 1, "docs.example.com"),)),
        synthesizer,
    ).run(TurnInput("问题", True, (), ()))

    assert "本地知识库部分检索未完成。" not in result.limitations
    assert web_overlap.is_set()


def _item(
    kind: str,
    number: int,
    *,
    score: float | None = None,
    published_at: str | None = None,
    quote: str | None = None,
    locator_value: str | None = None,
) -> EvidenceItem:
    locator_kind = (
        "url" if kind == "web" else "file" if kind == "session_file" else "chunk"
    )
    return EvidenceItem(
        evidence_id=f"ev-{kind}-{number}",
        source_kind=kind,
        title=f"{kind} {number}",
        locator_kind=locator_kind,
        locator_value=locator_value or f"{kind}-locator-{number}",
        quote=quote or f"{kind} 证据 {number}",
        published_at=published_at,
        score=score,
    )


def test_select_evidence_orders_globally_by_score_with_source_floor() -> None:
    from app.conversation.turn import _select_evidence

    knowledge = (
        _item("knowledge", 1, score=0.9),
        _item("knowledge", 2, score=0.8),
    )
    files = (_item("session_file", 1, score=0.95),)
    web = (
        _item("web", 1, score=0.85),
        _item("web", 2, score=0.2),
        _item("web", 3, score=0.1),
    )

    selected = _select_evidence(knowledge, files, web, limit=4)

    # 全局分数序：0.95(file) > 0.9(kb1) > 0.85(web1) > 0.8(kb2)
    assert [item.evidence_id for item in selected] == [
        "ev-session_file-1",
        "ev-knowledge-1",
        "ev-web-1",
        "ev-knowledge-2",
    ]


def test_select_evidence_guarantees_one_item_per_nonempty_source() -> None:
    from app.conversation.turn import _select_evidence

    knowledge = (_item("knowledge", 1, score=1.0),)
    files = (_item("session_file", 1, score=0.05),)
    web = tuple(_item("web", index, score=0.9 - index * 0.01) for index in range(1, 6))

    selected = _select_evidence(knowledge, files, web, limit=4)

    kinds = [item.source_kind for item in selected]
    # 低分 session_file 靠保底入选，其余按分数取 web
    assert kinds.count("session_file") == 1
    assert kinds.count("knowledge") == 1
    assert "ev-knowledge-1" in [item.evidence_id for item in selected]
    assert "ev-session_file-1" in [item.evidence_id for item in selected]


def test_select_evidence_aggregates_quotes_by_locator() -> None:
    from dataclasses import replace

    from app.conversation.turn import _aggregate_by_locator

    base = _item("web", 1, score=0.5, locator_value="https://a.example/x")
    second_query_hit = replace(
        base,
        evidence_id="ev-web-dup",
        quote="第二段补充内容。",
    )
    other = _item("web", 2, score=0.4, locator_value="https://a.example/y")

    aggregated = _aggregate_by_locator((base, second_query_hit, other))

    assert len(aggregated) == 2
    merged = next(item for item in aggregated if item.locator_value.endswith("/x"))
    assert "web 证据 1" in merged.quote
    assert "第二段补充内容。" in merged.quote


def test_published_at_breaks_score_ties_for_web_items() -> None:
    from datetime import datetime

    from app.conversation.turn import _evidence_rank

    older = _item("web", 1, score=0.5, published_at="2024-01-01T00:00:00+00:00")
    newer = _item("web", 2, score=0.5, published_at="2025-06-01T00:00:00+00:00")

    ranked = sorted([older, newer], key=_evidence_rank)

    assert ranked[0].evidence_id == "ev-web-2"
    assert datetime.fromisoformat(older.published_at).year == 2024


def test_normalized_scores_handles_rank_scale_and_clamps_unit_scale() -> None:
    from app.conversation.runtime import _normalized_scores, _rank_decay_scores

    # rank 型（>1）按本批最大值归一（批级判断）
    assert _normalized_scores([10.0, 5.0, 1.0]) == [1.0, 0.5, 0.1]
    assert _normalized_scores([1.2, 0.6]) == [1.0, 0.5]
    # 已是 [0,1] 型则截断到界内
    assert _normalized_scores([0.7, -0.3]) == [0.7, 0.0]
    assert _rank_decay_scores(3) == [1.0, 0.5, 1 / 3]


@pytest.mark.asyncio
async def test_tavily_retriever_assigns_rank_decay_scores() -> None:
    from app.conversation.runtime import TavilyEvidenceRetriever

    class Provider:
        def search(self, query, max_results=10, **kwargs):
            return type(
                "Result",
                (),
                {
                    "hits": [
                        type(
                            "Hit",
                            (),
                            {
                                "url": f"https://h.example/{i}",
                                "title": f"t{i}",
                                "content": f"内容 {i}。",
                            },
                        )()
                        for i in range(3)
                    ]
                },
            )()

    items = TavilyEvidenceRetriever(Provider()).search_sync("查询")
    assert [item.score for item in items] == [1.0, 0.5, 1 / 3]


def test_evidence_total_char_budget_drops_lowest_score_items() -> None:
    from app.conversation.turn import _enforce_total_budget

    items = tuple(
        _item("web", index, score=1.0 - index * 0.1, quote="字" * 10)
        for index in range(1, 6)
    )
    kept = _enforce_total_budget(items, budget=45)
    # 50 字符总量只保留高分的整条证据，低分整体剔除而非截断
    assert [item.evidence_id for item in kept] == [
        "ev-web-1",
        "ev-web-2",
        "ev-web-3",
        "ev-web-4",
    ]


def test_select_evidence_applies_total_character_budget_after_ranking() -> None:
    from app.conversation.turn import _select_evidence

    knowledge = (_item("knowledge", 1, score=0.9, quote="甲" * 100),)
    files = ()
    web = (
        _item("web", 1, score=0.8, quote="乙" * 5),
        _item("web", 2, score=0.7, quote="丙" * 900),
    )

    selected = _select_evidence(knowledge, files, web, limit=3, char_budget=150)

    # web2 整条被预算剔除，knowledge/web1 保留
    assert [item.evidence_id for item in selected] == ["ev-knowledge-1", "ev-web-1"]


@pytest.mark.asyncio
async def test_citation_validation_disabled_matches_legacy_path() -> None:
    """flag 关闭时行为与旧路径一致（B9 显式对齐测试）。"""
    item = evidence("knowledge", 1)
    draft = SynthesisDraft(
        sections=(SynthesisSection("回答。", (0,)),),
        claims=(SynthesisClaim("结论。", (item.evidence_id,)),),
        limitations=(),
    )

    legacy = build_engine(
        Planner(),
        Retriever((item,)),
        FileRetriever(()),
        Retriever(()),
        Synthesizer(draft),
    ).run(TurnInput("问题", False, (), ()))
    flagged_off = build_engine(
        Planner(),
        Retriever((item,)),
        FileRetriever(()),
        Retriever(()),
        Synthesizer(draft),
        citation_validation=False,
    ).run(TurnInput("问题", False, (), ()))

    left = await legacy
    right = await flagged_off
    assert left.answer == right.answer
    assert left.claims == right.claims
    assert left.evidence == right.evidence
    assert left.limitations == right.limitations


@pytest.mark.asyncio
async def test_citation_validation_drops_unsupported_claim() -> None:
    """flag 开启：编造无证据陈述的 claim 被裁剪并写入 limitation。"""
    # 中文 quote 与 good claim 有词面重叠；bad claim 词面完全无关 → 不获支持
    supported_item = EvidenceItem(
        "ev-knowledge-1",
        "knowledge",
        "文档",
        "chunk",
        "doc#1",
        quote="LangGraph 是一个用于构建智能体的框架，支持状态管理与检查点恢复。",
    )
    good_claim = SynthesisClaim("LangGraph 用于构建智能体框架。", ("ev-knowledge-1",))
    bad_claim = SynthesisClaim("某加密货币价格明天必然翻倍。", ("ev-knowledge-1",))
    draft = SynthesisDraft(
        sections=(
            SynthesisSection("直接回答。", (0,)),
            SynthesisSection("臆断段落。", (1,)),
        ),
        claims=(good_claim, bad_claim),
        limitations=(),
    )
    synthesizer = Synthesizer(draft)

    result = await build_engine(
        Planner(),
        Retriever((supported_item,)),
        FileRetriever(()),
        Retriever(()),
        synthesizer,
        citation_validation=True,
    ).run(TurnInput("问题", False, (), ()))

    assert "臆断段落" not in result.answer
    assert "直接回答" in result.answer
    assert any("未获证据支持" in item for item in result.limitations)
    assert len(result.claims) == 1


@pytest.mark.asyncio
async def test_citation_validation_keeps_supported_claims_intact() -> None:
    """flag 开启但全部 claim 均获支持：结果与旧路径等价。"""
    item = evidence("knowledge", 1)
    draft = SynthesisDraft(
        sections=(SynthesisSection("回答。", (0,)),),
        claims=(
            SynthesisClaim(
                "Evidence quote knowledge 1 相关陈述。", (item.evidence_id,)
            ),
        ),
        limitations=(),
    )

    result = await build_engine(
        Planner(),
        Retriever((item,)),
        FileRetriever(()),
        Retriever(()),
        Synthesizer(draft),
        citation_validation=True,
    ).run(TurnInput("问题", False, (), ()))

    assert result.answer.startswith("回答。")
    assert not any("未获证据支持" in item for item in result.limitations)


def test_citation_validation_settings_default_off() -> None:
    settings = ConversationSettings.from_env({})
    assert settings.enable_citation_validation is False
    enabled = ConversationSettings.from_env({"ENABLE_CITATION_VALIDATION": "true"})
    assert enabled.enable_citation_validation is True


@pytest.mark.asyncio
async def test_web_scores_are_renumbered_globally_across_queries() -> None:
    """多查询各给独立衰减分时，引擎合并后统一重编消除并列 1.0。"""
    hit_a = EvidenceItem(
        "ev-web-a",
        "web",
        "命中A",
        "url",
        "https://a.example/1",
        quote="A",
        hostname="a.example",
        score=1.0,
    )
    hit_b = EvidenceItem(
        "ev-web-b",
        "web",
        "命中B",
        "url",
        "https://b.example/1",
        quote="B",
        hostname="b.example",
        score=0.5,
    )
    hit_c = EvidenceItem(
        "ev-web-c",
        "web",
        "命中C",
        "url",
        "https://c.example/1",
        quote="C",
        hostname="c.example",
        score=1.0,  # 第二个查询的第 1 名
    )

    class MultiQueryRetriever:
        async def search(self, query: str, *, limit: int = 10):
            return {"q1": (hit_a, hit_b), "q2": (hit_c,)}.get(query, ())

    class MultiWebPlanner:
        async def plan(self, turn: TurnInput) -> TurnResearchPlan:
            return TurnResearchPlan(
                objective=turn.question,
                subquestions=(turn.question,),
                knowledge_queries=("knowledge query",),
                web_queries=("q1", "q2") if turn.use_web else (),
            )

    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0,)),),
            claims=(SynthesisClaim("结论。", ("ev-web-a",)),),
            limitations=(),
        )
    )

    await build_engine(
        MultiWebPlanner(),
        Retriever(()),
        FileRetriever(()),
        MultiQueryRetriever(),
        synthesizer,
    ).run(TurnInput("问题", True, (), ()))

    web_scores = [
        item.score for item in synthesizer.seen_evidence if item.source_kind == "web"
    ]
    assert web_scores == [1.0, 0.5, 1 / 3]


def test_apply_global_rank_decay_skips_knowledge_and_duplicates() -> None:
    from dataclasses import replace

    from app.conversation.turn import _apply_global_rank_decay

    kb_high = EvidenceItem(
        "ev-knowledge-1",
        "knowledge",
        "知识",
        "chunk",
        "doc#1",
        quote="k",
        score=0.87,
    )
    dup_first = EvidenceItem(
        "ev-web-dup",
        "web",
        "重复",
        "url",
        "https://d.example/1",
        quote="d1",
        hostname="d.example",
        score=0.5,
    )
    dup_second = replace(dup_first)
    other = EvidenceItem(
        "ev-web-x",
        "web",
        "其他",
        "url",
        "https://x.example/1",
        quote="x",
        hostname="x.example",
        score=None,
    )

    result = _apply_global_rank_decay((kb_high, dup_first, dup_second, other))

    assert next(i for i in result if i.evidence_id == "ev-knowledge-1").score == 0.87
    assert next(i for i in result if i.evidence_id == "ev-web-dup").score == 1.0
    assert next(i for i in result if i.evidence_id == "ev-web-x").score == 0.5


@pytest.mark.asyncio
async def test_uncovered_limitation_converges_to_latest_round() -> None:
    """多轮回环时"未覆盖问题"文案收敛为最新一条，不再逐轮累积。"""
    gaps = {1: "缺口一", 2: "缺口二", 3: "缺口三"}

    class Reviewer:
        calls = 0

        async def review(self, turn, plan, evidence_items, limitations):
            self.calls += 1
            done = self.calls >= len(gaps)
            return CoverageDecision(
                uncovered_questions=() if done else (gaps[self.calls],),
                knowledge_queries=() if done else (f"followup-{self.calls}",),
                web_queries=(),
            )

    knowledge = Retriever((evidence("knowledge", 1),))
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0,)),),
            claims=(SynthesisClaim("结论。", ("ev-knowledge-1",)),),
            limitations=(),
        )
    )

    result = await build_engine(
        Planner(), knowledge, FileRetriever(()), Retriever(()), synthesizer, Reviewer()
    ).run(TurnInput("问题", False, (), ()))

    # 第 1、2 次审阅记录了缺口文案；缺口在第 3 轮被补充证据解决，
    # 陈旧的"未覆盖问题"文案应随之消失而非残留
    uncovered_items = [
        item for item in result.limitations if item.startswith("未覆盖问题：")
    ]
    assert uncovered_items == []


@pytest.mark.asyncio
async def test_uncovered_limitation_keeps_only_latest_when_budget_exhausted() -> None:
    """预算耗尽且缺口仍在：多条历史"未覆盖问题"收敛为最新一条。"""

    class Reviewer:
        calls = 0

        async def review(self, turn, plan, evidence_items, limitations):
            self.calls += 1
            return CoverageDecision(
                uncovered_questions=(f"阶段缺口{self.calls}",),
                knowledge_queries=(f"unique-x{self.calls}",),
                web_queries=(),
            )

    knowledge = Retriever((evidence("knowledge", 1),))
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0,)),),
            claims=(SynthesisClaim("结论。", ("ev-knowledge-1",)),),
            limitations=(),
        )
    )

    result = await build_engine(
        Planner(), knowledge, FileRetriever(()), Retriever(()), synthesizer, Reviewer()
    ).run(TurnInput("问题", False, (), ()))

    uncovered_items = [
        item for item in result.limitations if item.startswith("未覆盖问题：")
    ]
    # 3 轮补充各产出一条，最终只剩第 4 次（路由退出前）审阅记录的最新一条
    assert uncovered_items == ["未覆盖问题：阶段缺口4"]


@pytest.mark.asyncio
async def test_user_knowledge_results_merge_into_knowledge_branch() -> None:
    """个人知识库（RAG 入库）结果并入 knowledge 分支并参与评分排序。"""
    main_item = evidence("knowledge", 1)
    user_upload = EvidenceItem(
        "ev-knowledge-upload-doc1-abc",
        "knowledge",
        "我的上传",
        "chunk",
        "upload-abc#section-0001",
        quote="个人库独有结论。",
        score=0.95,
    )

    class UploadRetriever:
        calls: list[str] = []

        async def search(self, query: str, *, limit: int = 10):
            UploadRetriever.calls.append(query)
            return (user_upload,)

    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0, 1)),),
            claims=(
                SynthesisClaim("主库结论。", ("ev-knowledge-1",)),
                SynthesisClaim("个人库结论。", ("ev-knowledge-upload-doc1-abc",)),
            ),
            limitations=(),
        )
    )

    await build_engine(
        Planner(),
        Retriever((main_item,)),
        None,
        Retriever(()),
        synthesizer,
    ).run(TurnInput("问题", False, (), ()))

    # 未注入时仅主库证据
    assert {item.evidence_id for item in synthesizer.seen_evidence} == {
        "ev-knowledge-1"
    }

    UploadRetriever.calls.clear()
    synthesizer.seen_evidence = []
    await build_engine(
        Planner(),
        Retriever((main_item,)),
        None,
        Retriever(()),
        synthesizer,
    ).run(TurnInput("问题", False, (), ()), user_knowledge=UploadRetriever())

    assert len(UploadRetriever.calls) == 1
    kinds = [item.source_kind for item in synthesizer.seen_evidence]
    assert all(kind == "knowledge" for kind in kinds)
    # 个人库高分证据排前
    assert synthesizer.seen_evidence[0].evidence_id == "ev-knowledge-upload-doc1-abc"


@pytest.mark.asyncio
async def test_supplemental_round_queries_personal_knowledge_library():
    class Reviewer:
        calls = 0

        async def review(self, turn, plan, evidence_items, limitations):
            self.calls += 1
            if self.calls == 1:
                return CoverageDecision(
                    uncovered_questions=("缺口",),
                    knowledge_queries=("followup-1",),
                    web_queries=(),
                )
            return CoverageDecision()

    knowledge = Retriever((evidence("knowledge", 1),))
    personal = Retriever((evidence("knowledge", 2),))
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0,)),),
            claims=(SynthesisClaim("结论。", ("ev-knowledge-1",)),),
            limitations=(),
        )
    )

    await build_engine(
        Planner(), knowledge, FileRetriever(()), Retriever(()), synthesizer, Reviewer()
    ).run(TurnInput("问题", False, (), ()), user_knowledge=personal)

    # G6：补充轮与首轮一致，主库与个人知识库都执行同一组补充查询
    assert knowledge.calls == ["knowledge query", "followup-1"]
    assert personal.calls == ["knowledge query", "followup-1"]


@pytest.mark.asyncio
async def test_planner_timeout_maps_to_model_timeout_code():
    class TimeoutPlanner:
        async def plan(self, turn: TurnInput) -> TurnResearchPlan:
            raise TimeoutError()

    engine = build_engine(
        TimeoutPlanner(),
        Retriever(()),
        FileRetriever(()),
        Retriever(()),
        Synthesizer(SynthesisDraft(sections=(), claims=(), limitations=())),
    )

    with pytest.raises(TurnExecutionError) as excinfo:
        await engine.run(TurnInput("问题", False, (), ()))
    assert excinfo.value.code == "model-timeout"


@pytest.mark.asyncio
async def test_synthesis_failure_degrades_to_evidence_snapshot():
    class FailingSynthesizer:
        async def synthesize(self, turn, plan, evidence_items, limitations):
            raise RuntimeError("synthesis model down")

    knowledge = Retriever((evidence("knowledge", 1),))
    engine = build_engine(
        Planner(), knowledge, FileRetriever(()), Retriever(()), FailingSynthesizer()
    )

    result = await engine.run(TurnInput("问题", False, (), ()))

    # B10-3：证据在手 → 降级为证据快照而非整轮失败
    assert result.answer.startswith("模型综合服务本轮未能完成整理")
    assert "knowledge source 1" in result.answer
    assert "Evidence quote knowledge 1" in result.answer
    assert result.claims == ()
    assert any("降级" in item for item in result.limitations)


@pytest.mark.asyncio
async def test_synthesis_failure_without_evidence_still_fails():
    class FailingSynthesizer:
        async def synthesize(self, turn, plan, evidence_items, limitations):
            raise RuntimeError("synthesis model down")

    engine = build_engine(
        Planner(), Retriever(()), FileRetriever(()), Retriever(()), FailingSynthesizer()
    )

    with pytest.raises(TurnExecutionError):
        await engine.run(TurnInput("问题", False, (), ()))


@pytest.mark.asyncio
async def test_plan_stage_event_carries_subquestions():

    knowledge = Retriever((evidence("knowledge", 1),))
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0,)),),
            claims=(SynthesisClaim("结论。", ("ev-knowledge-1",)),),
            limitations=(),
        )
    )
    events: list[dict] = []
    await build_engine(
        Planner(), knowledge, FileRetriever(()), Retriever(()), synthesizer
    ).run(TurnInput("问题", False, (), ()), emit=events.append)

    plan_events = [
        event
        for event in events
        if event["type"] == "stage.changed"
        and event.get("data", {}).get("subquestions")
    ]
    assert plan_events and plan_events[0]["data"]["subquestions"] == ["问题"]


@pytest.mark.asyncio
async def test_retrieval_progress_events_carry_evidence_counts() -> None:
    """B1 方案 D：首轮与每轮补充检索完成后推送'已找到 N 条证据'进度。"""
    knowledge = Retriever((evidence("knowledge", 1),))

    class Reviewer:
        calls = 0

        async def review(self, turn, plan, evidence_items, limitations):
            self.calls += 1
            done = self.calls >= 2
            return CoverageDecision(
                uncovered_questions=() if done else ("缺口",),
                knowledge_queries=() if done else ("followup",),
                web_queries=(),
            )

    knowledge_results = [evidence("knowledge", 2)]

    class CountingRetriever(Retriever):
        async def search(self, query: str, *, limit: int = 10):
            items = await super().search(query, limit=limit)
            return (*items, *knowledge_results)[: len(items) + 1]

    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0,)),),
            claims=(SynthesisClaim("结论。", ("ev-knowledge-1",)),),
            limitations=(),
        )
    )
    events: list[dict] = []

    await build_engine(
        Planner(),
        knowledge,
        None,
        Retriever(()),
        synthesizer,
        Reviewer(),
    ).run(TurnInput("问题", False, (), ()), emit=events.append)

    counts = [
        event.get("data", {}).get("evidence_count")
        for event in events
        if "已找到" in event.get("message", "")
    ]
    assert counts, "检索进度事件缺失"
    assert counts == sorted(counts, reverse=False), "证据计数应随回环递增"
    assert counts[0] >= 1


@pytest.mark.asyncio
async def test_planner_failure_is_retried_once_before_turn_fails() -> None:
    """ragmix X1 实证：planner 偶发 JSON 漂移一次即整轮失败——补对称重试。"""
    attempts = {"n": 0}

    class FlakyPlanner:
        async def plan(self, turn: TurnInput) -> TurnResearchPlan:
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise ValueError("model response is invalid")
            return TurnResearchPlan(turn.question, (), (turn.question,), ())

    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0,)),),
            claims=(SynthesisClaim("结论。", ("ev-knowledge-1",)),),
            limitations=(),
        )
    )

    result = await build_engine(
        FlakyPlanner(),
        Retriever((evidence("knowledge", 1),)),
        None,
        Retriever(()),
        synthesizer,
    ).run(TurnInput("问题", False, (), ()))

    assert attempts["n"] == 2
    assert result.answer.startswith("回答。")


@pytest.mark.asyncio
async def test_unsupported_sections_trigger_hinted_resynthesis() -> None:
    """R1 忠实度约束：无 claim 挂接的段落（S3 伪覆盖编造通道）触发
    带修正 hint 的第二次综合；修正后正常产出。"""
    good_item = EvidenceItem(
        "ev-knowledge-1",
        "knowledge",
        "文档",
        "chunk",
        "doc#1",
        quote="LangGraph 是一个用于构建智能体的框架，支持状态管理。",
    )

    class HintedSynthesizer:
        def __init__(self):
            self.calls: list[tuple[tuple[str, ...] | None]] = []
            self.hints: list[str] = []

        async def synthesize(
            self, turn, plan, evidence_items, limitations, *, on_delta=None
        ):
            self.calls.append(tuple(limitations))
            if len(self.calls) == 1:
                # 第一次：两段——有支撑段 + 编造段（无任何 claim 挂接）
                return SynthesisDraft(
                    sections=(
                        SynthesisSection("有支撑的正文。", (0,)),
                        SynthesisSection("无支撑的编造段落。", ()),
                    ),
                    claims=(SynthesisClaim("有支撑的结论。", ("ev-knowledge-1",)),),
                    limitations=(),
                )
            self.hints.append(limitations[-1] if limitations else "")
            return SynthesisDraft(
                sections=(SynthesisSection("修正后的正文。", (0,)),),
                claims=(SynthesisClaim("有支撑的结论。", ("ev-knowledge-1",)),),
                limitations=(),
            )

    synth = HintedSynthesizer()
    result = await build_engine(
        Planner(),
        Retriever((good_item,)),
        None,
        Retriever(()),
        synth,
    ).run(TurnInput("问题", False, (), ()))

    assert len(synth.calls) == 2, "应触发第二次综合"
    assert "无支撑的编造段落" in synth.hints[0], "重综合 hint 应携带未支撑段落文本"
    assert "无支撑的编造段落" not in result.answer
    assert any("未获证据支撑" in item for item in result.limitations) is False, (
        "第二次综合已修正，不应残留降级声明"
    )


@pytest.mark.asyncio
async def test_validation_strict_mode_prunes_unclaimed_fabricated_section() -> None:
    """ragmix S3 实证对齐：存在 UNSUPPORTED claim 时，无 claim 挂接的
    编造段落必须一并裁剪——否则正文残留纯编造文本。"""
    from app.conversation.turn import _finalize_draft_with_validation

    evidence_item = EvidenceItem(
        "ev-knowledge-1",
        "knowledge",
        "文档",
        "chunk",
        "doc#1",
        quote="LangGraph 是一个用于构建智能体的框架，支持状态管理与检查点恢复。",
    )
    good_claim = SynthesisClaim("LangGraph 用于构建智能体框架。", ("ev-knowledge-1",))
    fabricated_claim = SynthesisClaim(
        "某加密货币价格明天必然翻倍。", ("ev-knowledge-1",)
    )
    draft = SynthesisDraft(
        sections=(
            SynthesisSection("有支撑的正文。", (0,)),
            SynthesisSection("编造的段落：币价翻倍预言。", ()),
        ),
        claims=(good_claim, fabricated_claim),
        limitations=(),
    )

    result = _finalize_draft_with_validation(draft, (evidence_item,), ())

    assert "编造" not in result.answer, f"编造段落应被裁剪：{result.answer}"
    assert "有支撑" in result.answer
    assert len(result.claims) == 1
    assert any("未获证据支持" in item for item in result.limitations)


def test_select_evidence_reserves_quota_for_personal_uploads() -> None:
    """ragmix S4 实证（L2）：uploads 系证据绝对分（0.3x）在主库高分池
    （0.4-0.6）中被全局排序挤出 top6——select 级为 uploads 系保底 2 条。"""
    from app.conversation.turn import _select_evidence

    def main_item(number: int, score: float) -> EvidenceItem:
        return EvidenceItem(
            f"ev-knowledge-guide-{number}",
            "knowledge",
            f"主库 {number}",
            "chunk",
            f"guide#{number}",
            quote=f"主库证据 {number}",
            score=score,
        )

    def upload_item(number: int, score: float) -> EvidenceItem:
        return EvidenceItem(
            f"ev-knowledge-upload-{number}",
            "knowledge",
            f"个人库 {number}",
            "chunk",
            f"upload-{number}",
            quote=f"个人库证据 {number}",
            score=score,
        )

    knowledge = (
        main_item(1, 0.9),
        main_item(2, 0.85),
        main_item(3, 0.8),
        main_item(4, 0.75),
        main_item(5, 0.7),
        main_item(6, 0.65),
        main_item(7, 0.6),
        upload_item(1, 0.35),
        upload_item(2, 0.3),
    )

    selected = _select_evidence(knowledge, (), (), limit=6)

    ids = [item.evidence_id for item in selected]
    upload_kept = [i for i in ids if i.startswith("ev-knowledge-upload-")]
    # uploads 系保底 2 条进入 top6（纯分数序下 0.35/0.3 会被挤出）
    assert len(upload_kept) == 2, f"uploads 配额未生效：{ids}"
    # 主库高分仍占前位（全局分数序保持）
    assert ids[0] == "ev-knowledge-guide-1"


@pytest.mark.asyncio
async def test_citation_drops_trigger_hinted_resynthesis() -> None:
    """L2/B9 对齐：citation 判定 UNSUPPORTED 的陈述回传 hint 触发重综合，
    第二次综合产出可支撑表述后才 finalize（strict 兜底仍生效）。"""
    good_item = EvidenceItem(
        "ev-knowledge-1",
        "knowledge",
        "文档",
        "chunk",
        "doc#1",
        quote="LangGraph 是一个用于构建智能体的框架，支持状态管理。",
    )

    class CitationAwareSynthesizer:
        def __init__(self):
            self.limitations_seen: list[tuple[str, ...]] = []

        async def synthesize(
            self, turn, plan, evidence_items, limitations, *, on_delta=None
        ):
            self.limitations_seen.append(tuple(limitations))
            if len(self.limitations_seen) == 1:
                # 首轮：支撑段 + 编造段（编造 claim 挂真证据 id，词面零重叠）
                return SynthesisDraft(
                    sections=(
                        SynthesisSection("LangGraph 用于构建智能体框架。", (0,)),
                        SynthesisSection("某加密货币价格明天必然翻倍。", (1,)),
                    ),
                    claims=(
                        SynthesisClaim(
                            "LangGraph 用于构建智能体框架。", ("ev-knowledge-1",)
                        ),
                        SynthesisClaim(
                            "某加密货币价格明天必然翻倍。", ("ev-knowledge-1",)
                        ),
                    ),
                    limitations=(),
                )
            return SynthesisDraft(
                sections=(
                    SynthesisSection("LangGraph 用于构建智能体框架。", (0,)),
                    SynthesisSection("LangGraph 提供状态持久化能力。", (1,)),
                ),
                claims=(
                    SynthesisClaim(
                        "LangGraph 用于构建智能体框架。", ("ev-knowledge-1",)
                    ),
                    SynthesisClaim(
                        "LangGraph 提供状态持久化能力。", ("ev-knowledge-1",)
                    ),
                ),
                limitations=(),
            )

    synth = CitationAwareSynthesizer()
    result = await build_engine(
        Planner(),
        Retriever((good_item,)),
        None,
        Retriever(()),
        synth,
        citation_validation=True,
    ).run(TurnInput("问题", False, (), ()))

    assert len(synth.limitations_seen) == 2, "应触发第二次综合"
    # hint 携带编造陈述与判定原因进入第二次综合的 limitations
    hint = synth.limitations_seen[1][-1]
    assert "无证据支撑" in hint and "加密货币" in hint
    # 最终回答已不含编造内容
    assert "翻倍" not in result.answer
