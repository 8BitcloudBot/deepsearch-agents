import asyncio
from dataclasses import dataclass

import pytest

from app.conversation.contracts import EvidenceItem, TurnResearchPlan
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
    engine = TurnResearchEngine(Planner(), knowledge, files, web, synthesizer)

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
async def test_turn_graph_uses_session_files_and_web_when_requested() -> None:
    knowledge = Retriever((evidence("knowledge", 1),))
    files = FileRetriever((evidence("session_file", 1),))
    web = Retriever((evidence("web", 1, "docs.example.com"),))
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("综合回答。", (0,)),),
            claims=(
                SynthesisClaim(
                    "组合证据结论。",
                    ("ev-knowledge-1", "ev-session_file-1", "ev-web-1"),
                ),
            ),
            limitations=(),
        )
    )
    engine = TurnResearchEngine(Planner(), knowledge, files, web, synthesizer)

    await engine.run(
        TurnInput(
            question="结合文件和网络说明",
            use_web=True,
            attachment_ids=("file-1",),
            recent_history=(("上一问", "上一答"),),
        )
    )

    assert files.calls == [(("file-1",), "knowledge query")]
    assert web.calls == ["web query"]
    assert {item.source_kind for item in synthesizer.seen_evidence} == {
        "knowledge",
        "session_file",
        "web",
    }


@pytest.mark.asyncio
async def test_evidence_delivery_is_bounded_and_rotates_across_sources() -> None:
    knowledge = Retriever(tuple(evidence("knowledge", index) for index in range(1, 8)))
    files = FileRetriever(
        tuple(evidence("session_file", index) for index in range(1, 8))
    )
    web = Retriever(
        tuple(evidence("web", index, f"host{index}.example") for index in range(1, 8))
    )
    claims = tuple(
        SynthesisClaim(f"结论 {index}", (item.evidence_id,))
        for index, item in enumerate(
            (
                evidence("knowledge", 1),
                evidence("session_file", 1),
                evidence("web", 1, "host1.example"),
            )
        )
    )
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0, 1, 2)),),
            claims=claims,
            limitations=(),
        )
    )
    engine = TurnResearchEngine(Planner(), knowledge, files, web, synthesizer)

    await engine.run(
        TurnInput("问题", True, ("file-1",), ()),
    )

    assert len(synthesizer.seen_evidence) == 6
    assert [item.source_kind for item in synthesizer.seen_evidence[:3]] == [
        "knowledge",
        "session_file",
        "web",
    ]


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
    engine = TurnResearchEngine(
        Planner(), knowledge, FileRetriever(()), Retriever(()), synthesizer
    )

    result = await engine.run(TurnInput("问题", False, (), ()))

    assert result.answer.startswith("保留段落。")
    assert "删除段落" not in result.answer
    assert [claim.statement for claim in result.claims] == ["有效声明。"]


@pytest.mark.asyncio
async def test_external_evidence_with_zero_valid_claims_fails_explicitly() -> None:
    knowledge = Retriever((evidence("knowledge", 1),))
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("无引用回答。", (0,)),),
            claims=(SynthesisClaim("无效声明。", ("ev-unknown",)),),
            limitations=(),
        )
    )
    engine = TurnResearchEngine(
        Planner(), knowledge, FileRetriever(()), Retriever(()), synthesizer
    )

    with pytest.raises(TurnExecutionError, match="model-response-invalid"):
        await engine.run(TurnInput("问题", False, (), ()))


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
    engine = TurnResearchEngine(
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
    engine = TurnResearchEngine(
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
    engine = TurnResearchEngine(
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
            if len(started) == 3:
                all_started.set()
            await asyncio.wait_for(all_started.wait(), timeout=0.2)
            return self.results[:limit]

    class BlockingFiles(FileRetriever):
        async def search(self, attachment_ids, query, *, limit=10):
            self.calls.append((attachment_ids, query))
            started.add("session_file")
            if len(started) == 3:
                all_started.set()
            await asyncio.wait_for(all_started.wait(), timeout=0.2)
            return self.results[:limit]

    knowledge = BlockingRetriever("knowledge", (evidence("knowledge", 1),))
    files = BlockingFiles((evidence("session_file", 1),))
    web = BlockingRetriever("web", (evidence("web", 1, "docs.example.com"),))
    synthesizer = Synthesizer(
        SynthesisDraft(
            sections=(SynthesisSection("回答。", (0,)),),
            claims=(SynthesisClaim("结论。", ("ev-knowledge-1",)),),
            limitations=(),
        )
    )

    await TurnResearchEngine(
        Planner(), knowledge, files, web, synthesizer
    ).run(TurnInput("问题", True, ("file-1",), ()))

    assert started == {"knowledge", "session_file", "web"}


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

    await TurnResearchEngine(
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

    await TurnResearchEngine(
        ManyQueryPlanner(), knowledge, FileRetriever(()), web, synthesizer
    ).run(TurnInput("请做深入全面分析", True, (), ()))

    assert web.calls == ["web one", "web two", "web three"]
    assert len(synthesizer.seen_evidence) == 8


@pytest.mark.asyncio
async def test_complete_initial_coverage_skips_reviewer() -> None:
    class Reviewer:
        calls = 0

        async def review(self, turn, plan, evidence_items, limitations):
            self.calls += 1
            return CoverageDecision()

    reviewer = Reviewer()
    knowledge = Retriever(
        tuple(evidence("knowledge", index) for index in range(1, 3))
    )
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

    await TurnResearchEngine(
        Planner(), knowledge, FileRetriever(()), web, synthesizer, reviewer
    ).run(TurnInput("问题", True, (), ()))

    assert reviewer.calls == 0


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

    await TurnResearchEngine(
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

    await TurnResearchEngine(
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

    result = await TurnResearchEngine(
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

    result = await TurnResearchEngine(
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

    result = await TurnResearchEngine(
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
    result = await TurnResearchEngine(
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
    result = await TurnResearchEngine(
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
