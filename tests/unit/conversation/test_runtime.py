import json
from pathlib import Path

import pytest

from app.conversation.contracts import EvidenceItem, TurnResearchPlan
from app.conversation.runtime import (
    KnowledgeEvidenceRetriever,
    ModelCoverageReviewerAdapter,
    ModelPlannerAdapter,
    ModelSynthesizerAdapter,
    SessionFileEvidenceRetriever,
    TavilyEvidenceRetriever,
    build_conversation_application,
)
from app.conversation.turn import SynthesisDraft, TurnInput
from app.knowledge.contracts import KnowledgeChunk
from app.providers.contracts import SearchHit, SearchResult


def test_knowledge_adapter_maps_stable_chunk_identity() -> None:
    class Index:
        def search(self, query: str, *, limit: int = 10):
            return (
                KnowledgeChunk(
                    collection_id="guide",
                    document_id="langgraph",
                    chunk_id="intro",
                    title="LangGraph 入门",
                    content="图状态用于管理回合。",
                    score=0.91,
                    version="1.0.0",
                    section_path="概览",
                ),
            )

    result = KnowledgeEvidenceRetriever(Index()).search_sync("状态")
    assert result == (
        EvidenceItem(
            evidence_id="ev-knowledge-guide-langgraph-intro",
            source_kind="knowledge",
            title="LangGraph 入门",
            locator_kind="chunk",
            locator_value="langgraph#intro",
            quote="图状态用于管理回合。",
            score=0.91,
        ),
    )


def test_knowledge_adapter_extracts_query_relevant_passage() -> None:
    class Index:
        def search(self, query: str, *, limit: int = 10):
            return (
                KnowledgeChunk(
                    collection_id="guide",
                    document_id="langgraph",
                    chunk_id="long",
                    title="长文档",
                    content=(
                        "开头只介绍背景，与当前问题没有直接关系。\n\n"
                        "检查点可以持久化图状态，并支持中断后的恢复。\n\n"
                        "结尾是其他说明。"
                    ),
                    score=0.91,
                    version="1.0.0",
                    section_path="概览",
                ),
            )

    quote = KnowledgeEvidenceRetriever(Index()).search_sync("检查点 状态恢复")[0].quote

    assert quote.startswith("检查点可以持久化图状态")
    assert len(quote) <= 800


def test_default_application_build_is_provider_lazy(tmp_path: Path) -> None:
    application = build_conversation_application(
        {},
        runtime_root=tmp_path,
        store_path=tmp_path / "state.sqlite3",
        report_root=tmp_path / "reports",
    )
    assert application.store.path == tmp_path / "state.sqlite3"
    assert application.capabilities["model"]["status"] == "unavailable"
    assert application.capabilities["web"]["status"] == "unavailable"
    assert application.capabilities["knowledge"]["status"] == "unavailable"
    assert application.capabilities["session_file"]["status"] in {
        "ready",
        "unavailable",
    }


def test_tavily_adapter_converts_hits_and_caps_delivery() -> None:
    class Provider:
        def search(self, query: str, *, max_results: int = 5):
            return SearchResult(
                query=query,
                hits=(SearchHit("官方文档", "https://docs.example.dev/a", "短证据"),),
            )

    result = TavilyEvidenceRetriever(Provider()).search_sync("langgraph")
    assert result[0].evidence_id.startswith("ev-live-")
    assert result[0].source_kind == "web"
    assert result[0].locator_kind == "url"
    assert result[0].hostname == "docs.example.dev"


def test_tavily_adapter_passes_search_intent_and_candidate_limit() -> None:
    class Provider:
        def __init__(self):
            self.calls = []

        def search(self, query: str, *, max_results: int = 5, **kwargs):
            self.calls.append((query, max_results, kwargs))
            return SearchResult(query=query, hits=())

    provider = Provider()
    TavilyEvidenceRetriever(provider).search_sync("最新 LangGraph 发布", limit=8)

    assert provider.calls == [
        (
            "最新 LangGraph 发布",
            10,
            {"search_depth": "advanced", "topic": "news", "time_range": "month"},
        )
    ]


def test_session_file_retriever_uses_scoped_index() -> None:
    class Index:
        def __init__(self) -> None:
            self.calls = []

        def search(self, user_id, conversation_id, ids, query, *, limit=10):
            self.calls.append((user_id, conversation_id, ids, query, limit))
            return (
                KnowledgeChunk(
                    collection_id="session_files",
                    document_id="file-1",
                    chunk_id="section-0001-abc",
                    title="notes.md",
                    content="第一段：使用状态图。",
                    score=0.9,
                    version="1.0.0",
                    section_path="section-1",
                ),
            )

    user = type("User", (), {"id": "user-1"})()
    index = Index()

    result = SessionFileEvidenceRetriever(index, user, "conversation").search_sync(
        ("file-1",), "状态图"
    )
    assert index.calls == [("user-1", "conversation", ("file-1",), "状态图", 10)]
    assert result and result[0].source_kind == "session_file"
    assert result[0].locator_kind == "file"
    assert "状态图" in result[0].quote


def test_session_file_retriever_extracts_query_relevant_passage() -> None:
    class Index:
        def search(self, user_id, conversation_id, ids, query, *, limit=10):
            return (
                KnowledgeChunk(
                    collection_id="session_files",
                    document_id="file-1",
                    chunk_id="section-1",
                    title="notes.md",
                    content=(
                        "这是文件开头的背景。\n\n"
                        "评估集需要记录失败案例，才能持续比较检索质量。\n\n"
                        "最后是附录。"
                    ),
                    score=0.9,
                    version="1.0.0",
                    section_path="评估",
                ),
            )

    user = type("User", (), {"id": "user-1"})()
    quote = SessionFileEvidenceRetriever(
        Index(), user, "conversation"
    ).search_sync(("file-1",), "评估集 失败案例")[0].quote

    assert quote.startswith("评估集需要记录失败案例")
    assert len(quote) <= 800


@pytest.mark.asyncio
async def test_planner_invokes_model_once_per_turn_with_stable_payload() -> None:
    class Model:
        def __init__(self) -> None:
            self.calls: list[object] = []

        async def ainvoke(self, messages):
            self.calls.append(messages)
            return type(
                "Message",
                (),
                {
                    "content": (
                        '```json\n{"objective":"入门","subquestions":["概念"],'
                        '"knowledge_queries":["状态图"],'
                        '"web_queries":["LangGraph 官方"]}\n```'
                    )
                },
            )()

    model = Model()
    planner = ModelPlannerAdapter(model)

    plan = await planner.plan(TurnInput("如何入门", True, (), ()))
    await planner.plan(TurnInput("怎样继续？", False, (), (("如何入门", "先读文档"),)))

    assert plan.objective == "入门"
    assert plan.knowledge_queries == ("状态图",)
    assert len(model.calls) == 2
    system_prompt = model.calls[0][0]["content"]
    user_payload = json.loads(model.calls[0][1]["content"])
    assert "web_queries 必须为空" in system_prompt
    assert user_payload["question"] == "如何入门"
    assert user_payload["use_web"] is True
    assert user_payload["recent_history"] == []
    second_payload = json.loads(model.calls[1][1]["content"])
    assert second_payload["recent_history"] == [
        {"question": "如何入门", "answer": "先读文档"}
    ]
    # use_web=True 时透传模型给出的 web 查询；关闭态清空由 fail-closed 契约测试覆盖
    assert plan.knowledge_queries == ("状态图",)


def test_planner_disables_thinking_only_for_deepseek_model() -> None:
    copied: list[dict[str, object]] = []

    class Model:
        model_name = "deepseek-v4-flash"

        def model_copy(self, *, update):
            copied.append(update)
            return object()

    planner = ModelPlannerAdapter(Model())

    assert planner._model is not None
    assert copied == [
        {
            "extra_body": {"thinking": {"type": "disabled"}},
            "model_kwargs": {"response_format": {"type": "json_object"}},
        }
    ]


def test_planner_keeps_original_model_for_non_deepseek() -> None:
    class Model:
        model_name = "gpt-4.1-mini"

    model = Model()
    planner = ModelPlannerAdapter(model)

    assert planner._model is model


@pytest.mark.asyncio
async def test_model_coverage_reviewer_uses_bounded_evidence_summary() -> None:
    class Model:
        def __init__(self) -> None:
            self.messages = None

        async def ainvoke(self, messages):
            self.messages = messages
            return type(
                "Response",
                (),
                {
                    "content": (
                        '{"uncovered_questions":["缺口"],'
                        '"knowledge_queries":["补充一","补充二"],'
                        '"web_queries":["网络一","网络二"]}'
                    )
                },
            )()

    model = Model()
    reviewer = ModelCoverageReviewerAdapter(model)
    evidence_items = tuple(
        EvidenceItem(
            f"ev-{index}",
            "knowledge",
            f"文档 {index}",
            "chunk",
            f"doc#{index}",
            "证据" * 1000,
        )
        for index in range(10)
    )

    decision = await reviewer.review(
        TurnInput("问题", True, (), ()),
        TurnResearchPlan("目标", ("缺口",), ("原查询",), ("原网络查询",)),
        evidence_items,
        (),
    )

    assert decision.uncovered_questions == ("缺口",)
    assert decision.knowledge_queries == ("补充一",)
    assert decision.web_queries == ("网络一",)
    serialized = model.messages[1]["content"]
    assert len(serialized) < 5000
    assert "ev-7" in serialized
    assert "ev-8" not in serialized
    assert "recent_history" in json.loads(serialized)


@pytest.mark.asyncio
async def test_reviewer_and_synthesizer_payloads_carry_recent_history() -> None:
    empty_review = (
        '{"uncovered_questions":[],"knowledge_queries":[],"web_queries":[]}'
    )
    draft_json = (
        '{"answer_sections":[{"text":"答","claim_indexes":[0]}],'
        '"claims":[{"statement":"陈述","evidence_ids":["ev-1"]}],"limitations":[]}'
    )

    class Model:
        def __init__(self, content: str) -> None:
            self._content = content
            self.system = ""
            self.payload: dict[str, object] | None = None

        async def ainvoke(self, messages):
            self.system = messages[0]["content"]
            self.payload = json.loads(messages[1]["content"])
            return type("Response", (), {"content": self._content})()

    history = (("上一问", "上一答"), ("前前问", "前前答"))

    reviewer = Model(empty_review)
    await ModelCoverageReviewerAdapter(reviewer).review(
        TurnInput("新问题", True, (), history),
        TurnResearchPlan("目标", (), (), ()),
        (),
        (),
    )
    synthesizer = Model(draft_json)
    await ModelSynthesizerAdapter(synthesizer).synthesize(
        TurnInput("新问题", False, (), history),
        TurnResearchPlan("目标", (), (), ()),
        (EvidenceItem("ev-1", "knowledge", "文档", "chunk", "a#b", "原文"),),
        (),
    )

    expected = [
        {"question": "上一问", "answer": "上一答"},
        {"question": "前前问", "answer": "前前答"},
    ]
    # 无历史时字段为空列表也合法
    empty_history_review = Model(empty_review)
    await ModelCoverageReviewerAdapter(empty_history_review).review(
        TurnInput("首问", True, (), ()),
        TurnResearchPlan("目标", (), (), ()),
        (),
        (),
    )

    assert reviewer.payload["recent_history"] == expected
    assert synthesizer.payload["recent_history"] == expected
    assert empty_history_review.payload["recent_history"] == []
    # 系统提示词告知两个角色如何使用 recent_history
    assert "recent_history" in reviewer.system
    assert "确立" in reviewer.system
    assert "recent_history" in synthesizer.system
    assert "重复解释" in synthesizer.system


@pytest.mark.asyncio
async def test_model_synthesizer_returns_internal_draft_without_fence() -> None:
    class Model:
        messages = None

        async def ainvoke(self, messages):
            self.messages = messages
            return type(
                "Response",
                (),
                {
                    "content": (
                        '{"answer_sections":[{"text":"先理解状态图",'
                        '"claim_indexes":[0]}],"claims":[{"statement":'
                        '"状态图管理流程","evidence_ids":["ev-1"]}],'
                        '"limitations":[]}'
                    )
                },
            )()

    model = Model()
    draft = await ModelSynthesizerAdapter(model).synthesize(
        TurnInput("如何入门", False, (), ()),
        TurnResearchPlan("入门", (), (), ()),
        (EvidenceItem("ev-1", "knowledge", "文档", "chunk", "a#b", "原文"),),
        (),
    )
    assert isinstance(draft, SynthesisDraft)
    assert draft.sections[0].text == "先理解状态图"
    assert "400～800" in model.messages[0]["content"]
    assert "仅按允许列表执行" in model.messages[0]["content"]


@pytest.mark.asyncio
async def test_model_synthesizer_uses_deep_answer_budget() -> None:
    class Model:
        messages = None

        async def ainvoke(self, messages):
            self.messages = messages
            return type(
                "Response",
                (),
                {
                    "content": (
                        '{"answer_sections":[{"text":"深入回答",'
                        '"claim_indexes":[0]}],"claims":[{"statement":'
                        '"结论","evidence_ids":["ev-1"]}],"limitations":[]}'
                    )
                },
            )()

    model = Model()
    await ModelSynthesizerAdapter(model).synthesize(
        TurnInput("请详细深入分析", False, (), ()),
        TurnResearchPlan("入门", (), (), ()),
        (EvidenceItem("ev-1", "knowledge", "文档", "chunk", "a#b", "原文"),),
        (),
    )

    assert "800～1400" in model.messages[0]["content"]


def test_current_date_line_formats_iso_and_weekday() -> None:
    import datetime as dt

    from app.conversation.runtime import _current_date_line

    moment = dt.datetime(2026, 8, 27, tzinfo=dt.UTC)  # 周四
    line = _current_date_line(moment)
    assert line.startswith("今天是2026-08-27")
    assert "星期四" in line


@pytest.mark.asyncio
async def test_planner_prompt_injects_current_date() -> None:
    class Model:
        system = ""

        async def ainvoke(self, messages):
            self.system = messages[0]["content"]
            return type(
                "Response",
                (),
                {"content": '{"objective":"目标"}'},
            )()

    model = Model()
    await ModelPlannerAdapter(model).plan(TurnInput("问题", True, (), ()))
    assert model.system.startswith("今天是")


@pytest.mark.asyncio
async def test_planner_parses_research_intensity_and_hints() -> None:
    class Model:
        async def ainvoke(self, messages):
            return type(
                "Response",
                (),
                {
                    "content": (
                        '{"objective":"目标","research_intensity":"deep",'
                        '"search_hints":{"search_depth":"advanced","topic":"news"}}'
                    )
                },
            )()

    plan = await ModelPlannerAdapter(Model()).plan(TurnInput("问题", True, (), ()))

    assert plan.research_intensity == "deep"
    assert plan.hint("search_depth") == "advanced"
    assert plan.hint("topic") == "news"


@pytest.mark.asyncio
async def test_planner_drops_invalid_intensity_and_non_dict_hints() -> None:
    class Model:
        async def ainvoke(self, messages):
            return type(
                "Response",
                (),
                {
                    "content": (
                        '{"objective":"目标","research_intensity":"extreme",'
                        '"search_hints":"not-a-dict"}'
                    )
                },
            )()

    plan = await ModelPlannerAdapter(Model()).plan(TurnInput("问题", True, (), ()))

    assert plan.research_intensity is None
    assert plan.search_hints == ()


def test_plan_is_deep_prefers_planner_field_over_keywords() -> None:
    from app.conversation.turn import _plan_is_deep

    deep_plan = TurnResearchPlan(
        "目标",
        (),
        (),
        (),
        research_intensity="deep",
    )
    standard_plan = TurnResearchPlan(
        "目标",
        (),
        (),
        (),
        research_intensity="standard",
    )

    # 规划器字段生效时不再看关键词
    assert _plan_is_deep(deep_plan, "普通问题") is True
    assert _plan_is_deep(standard_plan, "请深入分析") is False
    # 字段缺失时回退关键词启发
    fallback = TurnResearchPlan("目标", (), (), ())
    assert _plan_is_deep(fallback, "请深入分析") is True
    assert _plan_is_deep(fallback, "普通问题") is False


def test_web_search_options_prefer_plan_hints() -> None:
    from app.conversation.runtime import _web_search_options

    hinted = TurnResearchPlan(
        "目标",
        (),
        (),
        (),
        search_hints=(("search_depth", "advanced"), ("topic", "news")),
    )

    options = _web_search_options("任意问题", hinted)

    assert options["search_depth"] == "advanced"
    assert options["topic"] == "news"

    # 无 hints 时回退关键词启发
    fallback_options = _web_search_options("最新进展是什么", None)
    assert fallback_options["topic"] == "news"


def test_tavily_retriever_passes_published_date_to_evidence() -> None:
    class Provider:
        def search(self, query, max_results=10, **kwargs):
            return SearchResult(
                query=query,
                hits=(
                    SearchHit(
                        "标题",
                        "https://docs.example.dev/x",
                        "正文内容。",
                        published_date="2026-08-01",
                    ),
                ),
            )

    items = TavilyEvidenceRetriever(Provider()).search_sync("查询")

    assert items[0].published_at == "2026-08-01"


def test_tavily_provider_parses_published_date_field() -> None:
    from unittest.mock import patch

    from app.providers.tavily import TavilyWebProvider

    provider = TavilyWebProvider("test-key")

    class FakeClient:
        def search(self, query, **kwargs):
            return {
                "results": [
                    {
                        "title": "t",
                        "url": "https://a.example/1",
                        "content": "c",
                        "published_date": "2026-07-30",
                    },
                    {"title": "t2", "url": "https://a.example/2", "content": "c2"},
                ]
            }

    with patch.object(provider, "_get_client", return_value=FakeClient()):
        result = provider.search("q")

    assert result.hits[0].published_date == "2026-07-30"
    assert result.hits[1].published_date is None
