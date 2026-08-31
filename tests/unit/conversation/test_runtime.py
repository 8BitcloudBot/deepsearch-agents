import json
from pathlib import Path

import pytest

from app.conversation.contracts import EvidenceItem, TurnResearchPlan
from app.conversation.runtime import (
    KnowledgeEvidenceRetriever,
    ModelCoverageReviewerAdapter,
    ModelPlannerAdapter,
    ModelSynthesizerAdapter,
    TavilyEvidenceRetriever,
    _web_search_options,
    build_conversation_application,
)
from app.conversation.settings import ConversationSettings
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
    # 会话附件路径已由知识库入库方案取代；键恒为 unavailable（T1）
    assert application.capabilities["session_file"]["status"] == "unavailable"


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
        extra_body: dict = {}
        model_kwargs: dict = {}

        def __init__(self) -> None:
            self.copies = copied

        def model_copy(self, *, update):
            clone = Model()
            clone.extra_body = {**self.extra_body, **update.get("extra_body", {})}
            clone.model_kwargs = {**self.model_kwargs, **update.get("model_kwargs", {})}
            self.copies.append(dict(update))
            return clone

    planner = ModelPlannerAdapter(Model())

    # 两次 copy 链式合并后：thinking 禁用与 response_format 同时就位
    assert planner._model.extra_body == {"thinking": {"type": "disabled"}}
    assert planner._model.model_kwargs == {"response_format": {"type": "json_object"}}
    # thinking 禁用已提升为共享函数（审阅器/标题同享），planner 侧
    # 叠加 response_format——两次 model_copy，最终语义与原单次等价
    assert copied == [
        {"extra_body": {"thinking": {"type": "disabled"}}},
        {"model_kwargs": {"response_format": {"type": "json_object"}}},
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
    empty_review = '{"uncovered_questions":[],"knowledge_queries":[],"web_queries":[]}'
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


@pytest.mark.asyncio
async def test_synthesizer_normalizes_dict_limitations_to_readable_text() -> None:
    class Model:
        async def ainvoke(self, messages):
            return type(
                "Response",
                (),
                {
                    "content": (
                        '{"answer_sections":[{"text":"答","claim_indexes":[0]}],'
                        '"claims":[{"statement":"陈述","evidence_ids":["ev-1"]}],'
                        '"limitations":['
                        '{"type": "source_sufficiency", "detail": "证据来源单一。"},'
                        '{"type": "other"},'
                        '"普通字符串限制"]}'
                    )
                },
            )()

    draft = await ModelSynthesizerAdapter(Model()).synthesize(
        TurnInput("问题", False, (), ()),
        TurnResearchPlan("目标", (), (), ()),
        (EvidenceItem("ev-1", "knowledge", "文档", "chunk", "a#b", "原文"),),
        (),
    )

    assert draft.limitations[0] == "证据来源单一。"
    # 无已知字段的对象退化为 ensure_ascii=False 的 JSON，而非 Python repr
    assert "'" not in draft.limitations[1]
    assert '"type"' in draft.limitations[1]
    assert draft.limitations[2] == "普通字符串限制"


def test_current_date_line_uses_local_date_when_no_now_given() -> None:
    import datetime as dt

    from app.conversation.runtime import _current_date_line

    line = _current_date_line()
    # G7：无参时使用服务器本地日期
    assert line.startswith(f"今天是{dt.date.today().isoformat()}（星期")


@pytest.mark.asyncio
async def test_synthesizer_budget_prefers_plan_intensity_over_keywords() -> None:
    class Model:
        messages = None

        async def ainvoke(self, messages):
            self.messages = messages
            return type(
                "Response",
                (),
                {
                    "content": (
                        '{"answer_sections":[{"text":"回答",'
                        '"claim_indexes":[0]}],"claims":[{"statement":'
                        '"结论","evidence_ids":["ev-1"]}],"limitations":[]}'
                    )
                },
            )()

    model = Model()
    # 问题含 deep 关键词，但规划器明确判 standard → 采纳规划器信号（G7）
    await ModelSynthesizerAdapter(model).synthesize(
        TurnInput("请详细深入分析", False, (), ()),
        TurnResearchPlan("入门", (), (), (), research_intensity="standard"),
        (EvidenceItem("ev-1", "knowledge", "文档", "chunk", "a#b", "原文"),),
        (),
    )
    assert "400～800" in model.messages[0]["content"]


def test_with_temperature_overrides_per_role() -> None:
    from dataclasses import dataclass, replace

    from app.conversation.runtime import _with_temperature

    @dataclass
    class FakeModel:
        temperature: float | None = 0.2

        def model_copy(self, update):
            return replace(self, **update)

    base = FakeModel()
    assert _with_temperature(base, None).temperature == 0.2
    assert _with_temperature(base, 0.7).temperature == 0.7
    assert base.temperature == 0.2  # 原实例不被修改


def test_settings_parses_per_role_temperature() -> None:
    from app.conversation.settings import ConversationSettings

    settings = ConversationSettings.from_env(
        {
            "MODEL_TEMPERATURE_PLANNER": "0.0",
            "MODEL_TEMPERATURE_SYNTHESIZER": "0.6",
        }
    )
    assert settings.model_temperature_planner == 0.0
    assert settings.model_temperature_synthesizer == 0.6
    assert settings.model_temperature_reviewer is None
    default = ConversationSettings.from_env({})
    assert default.model_temperature_planner is None


async def test_reviewer_receives_brief_history_while_synthesizer_full() -> None:
    from app.conversation.runtime import _history_records

    long_answer = "细" * 5000

    class Model:
        payloads = []

        async def ainvoke(self, messages):
            import json as _json

            self.payloads.append(_json.loads(messages[1]["content"]))
            return type("Response", (), {"content": '{"uncovered_questions":[]}'})()

    model = Model()
    evidence = (EvidenceItem("ev-1", "knowledge", "文档", "chunk", "a#b", "原文"),)
    plan = TurnResearchPlan("目标", (), (), ())
    turn = TurnInput("问题", False, (), (("问题", long_answer),))

    await ModelCoverageReviewerAdapter(model).review(turn, plan, evidence, ())
    reviewer_history = model.payloads[0]["recent_history"]
    assert reviewer_history[0]["answer"] == "细" * 300  # 审阅器吃摘要（H12）
    assert _history_records(turn)[0]["answer"] == long_answer  # 全量路径不变


def test_short_output_roles_carry_max_tokens_cap() -> None:
    from app.conversation.runtime import (
        ModelCoverageReviewerAdapter,
        ModelPlannerAdapter,
        ModelTitleAdapter,
    )

    class FakeModel:
        def bind(self, **kwargs):
            return ("bound", kwargs)

    assert ModelTitleAdapter(FakeModel())._model[1] == {"max_tokens": 200}
    assert ModelPlannerAdapter(FakeModel())._model[1] == {"max_tokens": 600}
    assert ModelCoverageReviewerAdapter(FakeModel())._model[1] == {"max_tokens": 800}


def test_reviewer_prompt_tightens_covered_judgement() -> None:
    from app.conversation.prompts import COVERAGE_REVIEWER_SYSTEM_PROMPT

    assert "不因表述措辞" in COVERAGE_REVIEWER_SYSTEM_PROMPT
    assert "必须为空数组" in COVERAGE_REVIEWER_SYSTEM_PROMPT


def test_light_model_routes_to_light_roles_and_keeps_synthesizer(monkeypatch) -> None:
    """分级模型路由：MODEL_NAME_LIGHT 配置时规划/审阅/标题用轻模型，综合器用主模型。"""
    from app.conversation import runtime as runtime_module

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            self.model_name = kwargs.get("model")
            self.model_copy_calls = 0

        def model_copy(self, *, update):
            self.model_copy_calls += 1
            clone = FakeChatOpenAI(model=self.model_name)
            clone.temperature = update.get("temperature")
            return clone

        def bind(self, **kwargs):
            return self

    monkeypatch.setattr("langchain_openai.ChatOpenAI", FakeChatOpenAI)

    environ = {
        "MODEL_NAME": "main-model",
        "MODEL_NAME_LIGHT": "lite-model",
        "MODEL_API_KEY": "k",  # pragma: allowlist secret — 测试假值
        "MODEL_TEMPERATURE_PLANNER": "0.1",
    }
    settings = ConversationSettings.from_env(environ)
    # 直接收紧构造路径：手动复刻装配段，断言三个角色拿到的实例
    from app.conversation.model import build_agent_model

    base_model, _ = build_agent_model(settings)
    light_model, _ = build_agent_model(
        settings, model_name_override=settings.model_name_light
    )
    planner = runtime_module.ModelPlannerAdapter(
        runtime_module._with_temperature(
            light_model, settings.model_temperature_planner
        )
    )
    synthesizer = runtime_module.ModelSynthesizerAdapter(
        runtime_module._with_temperature(
            base_model, settings.model_temperature_synthesizer
        )
    )
    reviewer = runtime_module.ModelCoverageReviewerAdapter(
        runtime_module._with_temperature(
            light_model, settings.model_temperature_reviewer
        )
    )

    assert planner._model.model_name == "lite-model"
    assert reviewer._model.model_name == "lite-model"
    assert synthesizer._model.model_name == "main-model"

    # 未配置 light 时全部共享主模型实例（现行为不变）
    settings_plain = ConversationSettings.from_env(
        {
            "MODEL_NAME": "main-model",
            "MODEL_API_KEY": "k",  # pragma: allowlist secret — 测试假值
        }
    )
    base_plain, _ = build_agent_model(settings_plain)
    planner_plain = runtime_module.ModelPlannerAdapter(
        runtime_module._with_temperature(
            base_plain, settings_plain.model_temperature_planner
        )
    )
    assert planner_plain._model is base_plain


def test_web_search_options_merge_fills_missing_keys_from_keywords() -> None:
    """C3：hints 只给部分键时，其余键由关键词启发补齐而非缺省 general。"""
    hinted = TurnResearchPlan(
        "目标",
        (),
        (),
        (),
        search_hints=(("time_range", "week"),),
    )

    # 查询含时效词：hints 未给 topic → 继承关键词启发的 news
    options = _web_search_options("Tavily 最近的更新是什么", hinted)
    assert options["time_range"] == "week"  # hints 显式值优先
    assert options["topic"] == "news"

    # 非时效查询且无 hints：回退原关键词路径
    assert _web_search_options("LangGraph 是什么")["topic"] == "general"


@pytest.mark.asyncio
async def test_streamed_synthesis_two_pass_produces_draft_and_deltas() -> None:
    """B1 方案A：正文流式增量透传，第二次调用抽取 claims 并锚回段落。"""
    seen_deltas: list[str] = []

    class StreamModel:
        async def astream(self, messages):
            for piece in ["LangGraph 管理", "回合状态。\n\n", "检查点支持恢复。"]:
                yield type("Chunk", (), {"content": piece})()

        async def ainvoke(self, messages):
            assert "引用抽取器" in messages[0]["content"]
            assert "LangGraph 管理回合状态。" in messages[1]["content"]
            return type(
                "Response",
                (),
                {
                    "content": (
                        '{"claims": ['
                        '{"statement": "LangGraph 管理回合状态。",'
                        ' "evidence_ids": ["ev-1"]}], '
                        '"limitations": [{"type": "t", "detail": "覆盖有限。"}]}'
                    )
                },
            )()

    plan = TurnResearchPlan("目标", (), (), ())
    evidence_item = EvidenceItem(
        "ev-1", "knowledge", "文档", "chunk", "doc#1", "LangGraph 原文。"
    )
    draft = await ModelSynthesizerAdapter(StreamModel(), streamed=True).synthesize(
        TurnInput("问题", False, (), ()),
        plan,
        (evidence_item,),
        (),
        on_delta=seen_deltas.append,
    )

    assert seen_deltas == ["LangGraph 管理", "回合状态。\n\n", "检查点支持恢复。"]
    assert [section.text for section in draft.sections] == [
        "LangGraph 管理回合状态。",
        "检查点支持恢复。",
    ]
    # claim statement 锚回第一段 → claim_indexes=[0]
    assert draft.sections[0].claim_indexes == (0,)
    assert draft.claims[0].evidence_ids == ("ev-1",)
    assert draft.limitations == ("覆盖有限。",)


@pytest.mark.asyncio
async def test_streamed_synthesis_falls_back_to_json_path_on_error() -> None:
    """流式任一步失败 → 回退 JSON 路径，draft 语义一致。"""
    calls: list[str] = []

    class BrokenStreamModel:
        async def astream(self, messages):
            calls.append("astream")
            raise RuntimeError("stream boom")
            yield  # pragma: no cover

        async def ainvoke(self, messages):
            calls.append("ainvoke")
            return type(
                "Response",
                (),
                {
                    "content": (
                        '{"answer_sections":[{"text":"JSON 回答","claim_indexes":[0]}],'
                        '"claims":[{"statement":"结论","evidence_ids":["ev-1"]}],'
                        '"limitations":[]}'
                    )
                },
            )()

    draft = await ModelSynthesizerAdapter(
        BrokenStreamModel(), streamed=True
    ).synthesize(
        TurnInput("问题", False, (), ()),
        TurnResearchPlan("目标", (), (), ()),
        (EvidenceItem("ev-1", "knowledge", "文档", "chunk", "doc#1", "原文"),),
        (),
        on_delta=lambda chunk: None,
    )

    assert calls == ["astream", "ainvoke"]
    assert draft.sections[0].text == "JSON 回答"


def test_streamed_flag_off_keeps_json_path() -> None:
    """flag off 时连 astream 都不会被触碰（调用形态与旧路径一致）。"""
    adapter = ModelSynthesizerAdapter(
        type("M", (), {"astream": lambda self, m: None})()
    )
    assert adapter._streamed is False


def test_light_roles_disable_deepseek_thinking(monkeypatch) -> None:
    """敌意测试（审阅器长度治理）：DeepSeek v4 系默认混合推理，思考 token
    不受 max_tokens 硬顶约束——审阅器/标题/规划器装配必须显式禁用 thinking，
    否则真机 reviewer completion 失控（实测 1896-3060 tokens/次）。"""

    class DeepseekModel:
        def __init__(self, name: str = "deepseek-v4-flash"):
            self.model_name = name
            self.extra_body: dict = {}
            self.copies: list[dict] = []

        def model_copy(self, *, update):
            clone = DeepseekModel(self.model_name)
            clone.extra_body = {**self.extra_body, **update.get("extra_body", {})}
            clone.temperature = update.get("temperature")
            self.copies.append(update)
            return clone

        def bind(self, **kwargs):
            return self

    from app.conversation import runtime as runtime_module

    base = DeepseekModel()
    light = DeepseekModel()
    # 模拟装配：审阅器/标题生成器应拿到禁用 thinking 的实例
    reviewer_model = runtime_module.ModelCoverageReviewerAdapter(
        runtime_module._without_deepseek_thinking(light)
    )._model
    thinking = reviewer_model.extra_body.get("thinking")
    assert isinstance(thinking, dict) and thinking["type"] == "disabled"

    # 非 DeepSeek 模型原样透传（不加 thinking 字段）
    plain = type("M", (), {"model_name": "gpt-compatible"})()
    assert runtime_module._without_deepseek_thinking(plain) is plain
    _ = base  # base_model（综合器）不受本修复约束，保持默认推理行为


def test_reviewer_binds_json_object_for_deepseek_only() -> None:
    """文档核对：DeepSeek response_format 仅 [text, json_object]——审阅器
    （严格 JSON 合同）在 DeepSeek 端点绑定该模式，非 DeepSeek 端点不绑。"""

    class DeepseekModel:
        model_name = "deepseek-v4-flash"
        model_kwargs: dict = {}

        def model_copy(self, *, update):
            clone = DeepseekModel()
            clone.model_kwargs = {**self.model_kwargs, **update.get("model_kwargs", {})}
            return clone

        def bind(self, **kwargs):
            return self

    reviewer = ModelCoverageReviewerAdapter(DeepseekModel())
    assert reviewer._model.model_kwargs == {"response_format": {"type": "json_object"}}

    class PlainModel:
        model_name = "gpt-compatible"

        def bind(self, **kwargs):
            return self

    plain = PlainModel()
    ModelCoverageReviewerAdapter(plain)
    assert not hasattr(plain, "model_kwargs")


def test_settings_default_model_is_deepseek_v4_flash():
    assert ConversationSettings().model_name == "deepseek-v4-flash"


@pytest.mark.asyncio
async def test_limitation_single_char_fragments_are_dropped() -> None:
    """防御：思考模式下模型偶发把整句拆成单字条目——碎片必须被剔除。"""

    class Model:
        async def ainvoke(self, messages):
            return type(
                "Response",
                (),
                {
                    "content": (
                        '{"answer_sections":[{"text":"答","claim_indexes":[0]}],'
                        '"claims":[{"statement":"陈述","evidence_ids":["ev-1"]}],'
                        '"limitations": ["现", "有", "证据不足", "", "冲突。"]}'
                    )
                },
            )()

    draft = await ModelSynthesizerAdapter(Model()).synthesize(
        TurnInput("问题", False, (), ()),
        TurnResearchPlan("目标", (), (), ()),
        (EvidenceItem("ev-1", "knowledge", "文档", "chunk", "a#b", "原文"),),
        (),
    )

    assert draft.limitations == ("证据不足", "冲突。")


@pytest.mark.asyncio
async def test_planner_truncates_over_limit_fields_instead_of_failing() -> None:
    """ragmix X1 实证：多主题对比题下模型常给 3+ 条知识库查询（每主题一条），
    合同上限 2 条——超限应截断降级而非整轮失败。"""

    class Model:
        async def ainvoke(self, messages):
            return type(
                "Response",
                (),
                {
                    "content": (
                        '{"objective":"对比","subquestions":["a","b","c","d"],'
                        '"knowledge_queries":["q1","q2","q3"],'
                        '"web_queries":["w1","w2","w3","w4"],'
                        '"research_intensity":"deep"}'
                    )
                },
            )()

    plan = await ModelPlannerAdapter(Model()).plan(TurnInput("问题", True, (), ()))

    assert len(plan.subquestions) == 3
    assert len(plan.knowledge_queries) == 2
    assert len(plan.web_queries) == 3
    assert plan.research_intensity == "deep"


@pytest.mark.asyncio
async def test_combined_knowledge_retriever_merges_and_tolerates_failure() -> None:
    """R2：共享业务库+个人库聚合——两库结果串联，单库异常静默跳过。"""
    from app.conversation.runtime import CombinedKnowledgeRetriever

    class OkRetriever:
        async def search(self, query: str, *, limit: int = 10):
            return (
                EvidenceItem(
                    "ev-a", "knowledge", "业务库", "chunk", "doc#a", "内容A", score=0.8
                ),
            )

    class BrokenRetriever:
        async def search(self, query: str, *, limit: int = 10):
            raise RuntimeError("sub-retriever down")

    combined = CombinedKnowledgeRetriever((OkRetriever(), BrokenRetriever()))
    items = await combined.search("查询")

    assert [i.evidence_id for i in items] == ["ev-a"]


def test_shared_knowledge_user_constant() -> None:
    from app.conversation.uploads import SHARED_KNOWLEDGE_USER

    assert SHARED_KNOWLEDGE_USER == "shared"


def test_long_query_is_truncated_before_index_search() -> None:
    """ragmix F1：长查询 dense 语义稀释致零命中——检索前截断规范化。"""

    class RecordingIndex:
        def __init__(self):
            self.queries: list[str] = []

        def search(self, query: str, *, limit: int = 10):
            self.queries.append(query)
            return ()

    long_query = "RagFlow 核心特性有哪些 " + "自托管部署的系统要求细节 " * 6
    index = RecordingIndex()
    KnowledgeEvidenceRetriever(index).search_sync(long_query)

    sent = index.queries[0]
    assert len(sent) <= 64 + 1, f"长查询未截断：len={len(sent)}"
    assert sent.startswith("RagFlow 核心特性有哪些")
    assert "系统要求细节" not in sent[64:]
