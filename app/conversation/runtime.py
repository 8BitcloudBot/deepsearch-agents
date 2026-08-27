"""Provider adapters for the bounded schema 5.0 conversation graph.

Adapters deliberately expose only short evidence snippets to the graph. Provider
SDKs and file parsers remain behind this module so the turn engine can be tested
without network or model credentials.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from app.conversation.contracts import EvidenceItem, TurnResearchPlan
from app.conversation.heuristics import is_deep_request as _is_deep_request
from app.conversation.turn import (
    CoverageDecision,
    SynthesisClaim,
    SynthesisDraft,
    SynthesisSection,
    TurnInput,
)

_FENCE_RE = re.compile(
    r"^```(?:json)?\s*\n(?P<body>.*?)\n```$", re.DOTALL | re.IGNORECASE
)
_MAX_QUOTE = 2000
_EXCERPT_PARAGRAPHS = 2  # 每次摘录取查询词密度最高的前 N 个段落
_MAX_COVERAGE_QUOTE = 300


class _UnavailablePlanner:
    async def plan(self, turn: TurnInput) -> TurnResearchPlan:
        raise RuntimeError("research model unavailable")


class _UnavailableSynthesizer:
    async def synthesize(self, turn, plan, evidence_items, limitations):
        raise RuntimeError("research model unavailable")


class _UnavailableRetriever:
    async def search(self, query: str, *, limit: int = 10):
        raise RuntimeError("provider unavailable")


def _response_text(response: Any) -> str:
    value = getattr(response, "content", response)
    if isinstance(value, list):
        value = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in value
        )
    if not isinstance(value, str) or not value.strip():
        raise ValueError("model response is invalid")
    return value.strip()


def _strict_json(response: Any) -> dict[str, Any]:
    raw = _response_text(response)
    match = _FENCE_RE.fullmatch(raw)
    if match:
        raw = match.group("body").strip()
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("model response is invalid") from exc
    if not isinstance(payload, dict):
        raise ValueError("model response is invalid")
    return payload


def _history_records(turn: TurnInput) -> list[dict[str, str]]:
    return [
        {"question": question, "answer": answer}
        for question, answer in turn.recent_history
    ]


def _current_date_line(now: Any = None) -> str:
    """组装期注入当前日期（ISO + 星期），供所有角色 system prompt 头部使用。"""
    import datetime as dt

    moment = now or dt.datetime.now(dt.UTC)
    weekdays = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")
    iso = moment.astimezone(dt.UTC).date().isoformat()
    weekday = weekdays[moment.weekday()]
    return f"今天是{iso}（{weekday}）。"


class ModelPlannerAdapter:
    _SYSTEM_PROMPT = (
        "你是一名严谨的研究规划器。给定用户问题与近几轮对话，输出一份研究计划。\n"
        "\n"
        "方法要求：\n"
        "1. 先判断问题的类型（事实查证 / 定义解释 / 多实体对比 / 时效动态 / 步骤教程），据此决定搜索侧重；\n"
        "2. 将问题拆解为回答所必需的子问题，去掉可有可无的枝节；每轮至多 3 个子问题、2 个知识库查询、3 个网络查询；\n"
        "3. 网络查询要具体、可命中（避免过宽的单词查询），时效类信息加年份或“最新”；权威事实类优先官方文档/规范；\n"
        "4. 注意 recent_history：已经确立的事实不要再列入子问题；\n"
        "5. 当本轮关闭 Web 时，web_queries 必须为空；research_intensity 取 standard 或 deep——"
        "涉及多步论证、比较多个主体或用户明示要深入分析时取 deep。\n"
        "\n"
        "只返回 JSON 对象，字段：objective、subquestions、knowledge_queries、web_queries、"
        "research_intensity、search_hints（可选）。不调用任何工具，不委派任务，不输出 JSON 以外的内容。"
    )

    def __init__(self, model: Any):
        planner_model = model
        model_name = str(getattr(model, "model_name", "")).casefold()
        if "deepseek" in model_name and callable(getattr(model, "model_copy", None)):
            extra_body = dict(getattr(model, "extra_body", None) or {})
            extra_body["thinking"] = {"type": "disabled"}
            model_kwargs = dict(getattr(model, "model_kwargs", None) or {})
            model_kwargs["response_format"] = {"type": "json_object"}
            planner_model = model.model_copy(
                update={"extra_body": extra_body, "model_kwargs": model_kwargs}
            )
        self._model = planner_model

    async def plan(self, turn: TurnInput) -> TurnResearchPlan:
        response = await self._model.ainvoke(
            [
                {
                    "role": "system",
                    "content": _current_date_line() + "\n" + self._SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": turn.question,
                            "use_web": turn.use_web,
                            "recent_history": _history_records(turn),
                        },
                        ensure_ascii=False,
                    ),
                },
            ]
        )
        payload = _strict_json(response)
        try:
            intensity = payload.get("research_intensity")
            hints = payload.get("search_hints")
            return TurnResearchPlan(
                objective=payload["objective"],
                subquestions=tuple(payload.get("subquestions", ())),
                knowledge_queries=tuple(payload.get("knowledge_queries", ())),
                web_queries=(
                    tuple(payload.get("web_queries", ())) if turn.use_web else ()
                ),
                research_intensity=(
                    intensity if intensity in ("standard", "deep") else None
                ),
                search_hints=(
                    tuple(hints.items()) if isinstance(hints, dict) else ()
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("model response is invalid") from exc


class ModelCoverageReviewerAdapter:
    def __init__(self, model: Any):
        self._model = model

    async def review(
        self,
        turn: TurnInput,
        plan: TurnResearchPlan,
        evidence_items: tuple[EvidenceItem, ...],
        limitations: tuple[str, ...],
    ) -> CoverageDecision:
        evidence = [
            {
                "evidence_id": item.evidence_id,
                "source_kind": item.source_kind,
                "title": item.title,
                "quote": item.quote[:_MAX_COVERAGE_QUOTE],
            }
            for item in evidence_items[:8]
        ]
        response = await self._model.ainvoke(
            [
                {
                    "role": "system",
                    "content": _current_date_line()
                    + "\n"
                    + (
                        "你是证据覆盖审阅器。对照研究计划的子问题和已有证据，"
                        "判断哪些部分仍未被证据支撑，并生成少量补充查询。\n"
                        "\n"
                        "规则：\n"
                        "1. 逐一核对每个子问题：covered（有直接支撑）/ partial（只有间接或片面支撑）/"
                        "uncovered（没有证据触及）；\n"
                        "2. uncovered_questions 只收录 partial 与 uncovered 的子问题，至多 3 个，按重要性排序；\n"  # noqa: E501
                        "3. 每个未覆盖子问题对每类来源至多生成一条查询，查询不得与研究计划和已有记录重复；\n"
                        "4. 如果证据总体充分（关键主张均有出处），uncovered_questions 返回空数组。\n"
                        "\n"
                        "仅返回 JSON：uncovered_questions、knowledge_queries、web_queries。"
                        "recent_history 为此前数轮问答摘录；已在其中确立的事实不要再当作未覆盖问题。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": turn.question,
                            "use_web": turn.use_web,
                            "recent_history": _history_records(turn),
                            "plan": plan.as_dict(),
                            "evidence": evidence,
                            "limitations": list(limitations),
                        },
                        ensure_ascii=False,
                    ),
                },
            ]
        )
        payload = _strict_json(response)
        try:
            uncovered = tuple(payload.get("uncovered_questions", ()))[:3]
            maximum = len(uncovered)
            return CoverageDecision(
                uncovered_questions=uncovered,
                knowledge_queries=tuple(payload.get("knowledge_queries", ()))[:maximum],
                web_queries=(
                    tuple(payload.get("web_queries", ()))[:maximum]
                    if turn.use_web
                    else ()
                ),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("model response is invalid") from exc


class ModelSynthesizerAdapter:
    def __init__(self, model: Any):
        self._model = model

    async def synthesize(
        self,
        turn: TurnInput,
        plan: TurnResearchPlan,
        evidence_items: tuple[EvidenceItem, ...],
        limitations: tuple[str, ...],
    ) -> SynthesisDraft:
        evidence = [
            {
                "evidence_id": item.evidence_id,
                "source_kind": item.source_kind,
                "title": item.title,
                "quote": item.quote[:_MAX_QUOTE],
                "locator": item.locator_value,
                "published_at": item.published_at,
            }
            for item in evidence_items
        ]
        answer_budget = (
            "800～1400"
            if _is_deep_request(turn.question)
            else "400～800"
        )
        response = await self._model.ainvoke(
            [
                {
                    "role": "system",
                    "content": _current_date_line()
                    + "\n"
                    + (
                        "你是研究综合撰写人。根据证据集与既定计划撰写回答。\n"
                        "\n"
                        "要求：\n"
                        "1. 用自然、连贯的中文段落直接回答用户的问题；开头给出结论，再展开论据；不复述内部结构；\n"
                        "2. 每个事实性陈述都必须挂接 claims，claims.statement 对应答案中的一句话要点，"
                        "evidence_ids 只能来自给出的证据 ID；一段 text 通过 claim_indexes 关联若干 claim；\n"  # noqa: E501
                        "3. 结合 recent_history 自然承接前文，不重复解释已确立的概念；\n"
                        "4. 证据之间冲突时如实呈现分歧而不是擅自裁决，并把冲突写入 limitations；\n"
                        "5. 信息可能因时间而变化的部分，利用证据中的时间信息谨慎表述（“截至…”）；\n"
                        "6. 涉及权限或安全限制的话题统一表述为“仅按允许列表执行”，不使用其他同义措辞；\n"
                        f"7. 回答长度控制在约 {answer_budget} 个中文字符。\n"
                        "\n"
                        "仅返回 JSON：answer_sections、claims、limitations。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": turn.question,
                            "recent_history": _history_records(turn),
                            "plan": plan.as_dict(),
                            "evidence": evidence,
                            "limitations": list(limitations),
                        },
                        ensure_ascii=False,
                    ),
                },
            ]
        )
        payload = _strict_json(response)
        try:
            raw_sections = payload["answer_sections"]
            raw_claims = payload["claims"]
            raw_limitations = payload.get("limitations", [])
            if not isinstance(raw_sections, list) or not isinstance(raw_claims, list):
                raise ValueError
            sections = tuple(
                SynthesisSection(
                    text=item["text"],
                    claim_indexes=tuple(item.get("claim_indexes", ())),
                )
                for item in raw_sections
                if isinstance(item, dict)
            )
            claims = tuple(
                SynthesisClaim(
                    statement=item["statement"],
                    evidence_ids=tuple(item.get("evidence_ids", ())),
                )
                for item in raw_claims
                if isinstance(item, dict)
            )
            if len(sections) != len(raw_sections) or len(claims) != len(raw_claims):
                raise ValueError
            if not isinstance(raw_limitations, list):
                raise ValueError
            return SynthesisDraft(
                sections, claims, tuple(str(item) for item in raw_limitations)
            )
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise ValueError("model response is invalid") from exc


def _normalized_scores(values: list[float]) -> list[float]:
    """Clamp provider scores into [0, 1]; rank-style scales (>1) use batch max."""
    if not values:
        return []
    maximum = max(values)
    if maximum > 1:
        return [max(value, 0.0) / maximum for value in values]
    return [min(max(value, 0.0), 1.0) for value in values]


def _rank_decay_scores(count: int) -> list[float]:
    return [1 / (index + 1) for index in range(count)]


class KnowledgeEvidenceRetriever:
    def __init__(self, index: Any):
        self._index = index

    def search_sync(self, query: str, *, limit: int = 10) -> tuple[EvidenceItem, ...]:
        chunks = self._index.search(query, limit=min(10, limit))
        scores = _normalized_scores([chunk.score for chunk in chunks])
        result: list[EvidenceItem] = []
        for chunk, score in zip(chunks, scores):
            key = f"{chunk.collection_id}-{chunk.document_id}-{chunk.chunk_id}"
            safe_key = re.sub(r"[^A-Za-z0-9_.:-]+", "-", key)
            result.append(
                EvidenceItem(
                    evidence_id=f"ev-knowledge-{safe_key}",
                    source_kind="knowledge",
                    title=chunk.title,
                    locator_kind="chunk",
                    locator_value=f"{chunk.document_id}#{chunk.chunk_id}",
                    quote=_relevant_excerpt(chunk.content, query),
                    score=score,
                )
            )
        return tuple(result)

    async def search(self, query: str, *, limit: int = 10) -> tuple[EvidenceItem, ...]:
        import asyncio

        return await asyncio.to_thread(self.search_sync, query, limit=limit)


class TavilyEvidenceRetriever:
    def __init__(self, provider: Any, plan_provider: Any = None):
        self._provider = provider
        self._plan_provider = plan_provider

    def search_sync(self, query: str, *, limit: int = 10) -> tuple[EvidenceItem, ...]:
        options = _web_search_options(
            query, self._plan_provider() if self._plan_provider else None
        )
        parameters = inspect.signature(self._provider.search).parameters
        supports_options = any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        ) or all(name in parameters for name in options)
        result = self._provider.search(
            query,
            max_results=10,
            **(options if supports_options else {}),
        )
        items: list[EvidenceItem] = []
        hits = result.hits[:5]
        scores = _rank_decay_scores(len(hits))
        for hit, score in zip(hits, scores):
            digest = hashlib.sha1(
                hit.url.encode("utf-8"), usedforsecurity=False
            ).hexdigest()[:16]
            hostname = urlsplit(hit.url).hostname
            items.append(
                EvidenceItem(
                    evidence_id=f"ev-live-{digest}",
                    source_kind="web",
                    title=hit.title or hostname or "Web 来源",
                    locator_kind="url",
                    locator_value=hit.url,
                    quote=_relevant_excerpt(hit.content, query),
                    hostname=hostname,
                    score=score,
                )
            )
        return tuple(items)

    async def search(self, query: str, *, limit: int = 10) -> tuple[EvidenceItem, ...]:
        import asyncio

        return await asyncio.to_thread(self.search_sync, query, limit=limit)


def _web_search_options(query: str, plan: Any = None) -> dict[str, str]:
    """规划器 search_hints 优先；缺失/非法时回退关键词启发。"""
    if plan is not None and getattr(plan, "search_hints", None):
        options: dict[str, str] = {}
        for key in ("search_depth", "topic", "time_range"):
            value = plan.hint(key)
            if isinstance(value, str) and value.strip():
                options[key] = value.strip()
        if options:
            if "search_depth" not in options:
                options["search_depth"] = "basic"
            return options
    folded = query.casefold()
    current_terms = (
        "最新",
        "目前",
        "近期",
        "最近",
        "发布",
        "today",
        "latest",
        "current",
    )
    official_terms = ("官方", "文档", "规范", "标准", "repository", "github", "docs")
    current = any(term in folded for term in current_terms)
    advanced = current or any(term in folded for term in official_terms)
    result = {
        "search_depth": "advanced" if advanced else "basic",
        "topic": "news" if current else "general",
    }
    if current:
        result["time_range"] = "month"
    return result


def _relevant_excerpt(content: str, query: str) -> str:
    """Select a compact query-relevant passage from provider Markdown."""
    paragraphs = [
        re.sub(r"\s+", " ", part).strip()
        for part in re.split(r"\n\s*\n|(?<=[.!?。！？])\s+", content)
        if part.strip()
    ]
    if not paragraphs:
        return content[:_MAX_QUOTE]
    terms = {
        term.casefold()
        for term in re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}", query)
    }
    ranked = sorted(
        enumerate(paragraphs),
        key=lambda pair: (
            -sum(term in pair[1].casefold() for term in terms),
            pair[0],
        ),
    )
    chosen = [
        ranked[index][1] for index in range(min(_EXCERPT_PARAGRAPHS, len(ranked)))
    ]
    return "\n".join(chosen)[:_MAX_QUOTE]


class SessionFileEvidenceRetriever:
    def __init__(self, index: Any, user: Any, conversation_id: str):
        self._index = index
        self._user = user
        self._conversation_id = conversation_id

    def search_sync(
        self, attachment_ids: tuple[str, ...], query: str, *, limit: int = 10
    ) -> tuple[EvidenceItem, ...]:
        if self._user is None or not self._conversation_id:
            return ()
        chunks = self._index.search(
            self._user.id,
            self._conversation_id,
            attachment_ids,
            query,
            limit=limit,
        )
        scores = _rank_decay_scores(len(chunks))
        return tuple(
            EvidenceItem(
                evidence_id=f"ev-file-{chunk.document_id}-{chunk.chunk_id}",
                source_kind="session_file",
                title=chunk.title,
                locator_kind="file",
                locator_value=f"{chunk.title}:{chunk.section_path or chunk.chunk_id}",
                quote=_relevant_excerpt(chunk.content, query),
                score=score,
            )
            for chunk, score in zip(chunks, scores)
        )

    async def search(
        self, attachment_ids: tuple[str, ...], query: str, *, limit: int = 10
    ) -> tuple[EvidenceItem, ...]:
        import asyncio

        return await asyncio.to_thread(
            self.search_sync, attachment_ids, query, limit=limit
        )


def build_conversation_application(
    environ: Any,
    *,
    runtime_root: Path,
    store_path: str | Path,
    report_root: str | Path,
):
    """Assemble the bounded graph without contacting any provider at startup."""
    from app.conversation.application import ConversationApplication
    from app.conversation.report import ConversationReport
    from app.conversation.settings import ConversationSettings
    from app.conversation.store import ConversationStore
    from app.conversation.turn import TurnResearchEngine

    settings = ConversationSettings.from_env(environ)
    store = ConversationStore(store_path)
    report = ConversationReport(report_root, store)

    planner: Any = _UnavailablePlanner()
    synthesizer: Any = _UnavailableSynthesizer()
    model_ready = False
    if settings.model_api_key:
        try:
            from app.conversation.model import build_agent_model

            model, _ = build_agent_model(settings)
            planner = ModelPlannerAdapter(model)
            synthesizer = ModelSynthesizerAdapter(model)
            coverage_reviewer = ModelCoverageReviewerAdapter(model)
            model_ready = True
        except Exception:
            planner = _UnavailablePlanner()
            synthesizer = _UnavailableSynthesizer()
            coverage_reviewer = None
    else:
        coverage_reviewer = None

    knowledge: Any = _UnavailableRetriever()
    file_index: Any = None
    knowledge_ready = False
    session_file_ready = False
    try:
        from app.knowledge.contracts import (
            KnowledgeIndexSpec,
            resolve_knowledge_index_path,
        )
        from app.knowledge.embeddings import FastEmbedEmbeddingAdapter
        from app.knowledge.qdrant_local import QdrantLocalKnowledgeIndex

        embedder = FastEmbedEmbeddingAdapter(
            model=settings.knowledge.embedding_model,
            version="0.8.0",
            dimension=384,
            cache_dir=str(runtime_root / ".cache" / "fastembed"),
        )
        spec = KnowledgeIndexSpec(
            collection_id=settings.knowledge.collection,
            embedding=embedder.descriptor,
            distance="cosine",
            chunking_version="semantic-markdown-v1",
        )
        index_path = resolve_knowledge_index_path(
            settings.knowledge.index_path, runtime_root=runtime_root
        )
        ready, _ = QdrantLocalKnowledgeIndex.check_readiness(index_path, spec)
        if ready:
            knowledge = KnowledgeEvidenceRetriever(
                QdrantLocalKnowledgeIndex(
                    index_path, spec, embedder, min_score=settings.knowledge.min_score
                )
            )
            knowledge_ready = True
        from app.conversation.file_index import SessionFileIndex

        file_index = SessionFileIndex(
            runtime_root / ".data" / "session-file-index", embedder
        )
        session_file_ready = True
    except Exception:
        knowledge = _UnavailableRetriever()

    web: Any = _UnavailableRetriever()
    web_ready = False
    if settings.tavily_api_key:
        try:
            from app.providers.tavily import TavilyWebProvider

            web = TavilyEvidenceRetriever(
                TavilyWebProvider(settings.tavily_api_key)
            )
            web_ready = True
        except Exception:
            web = _UnavailableRetriever()

    files = SessionFileEvidenceRetriever(file_index, None, "")
    engine = TurnResearchEngine(
        planner,
        knowledge,
        files,
        web,
        synthesizer,
        coverage_reviewer,
        citation_validation=settings.enable_citation_validation,
    )
    return ConversationApplication(
        store,
        engine,
        report,
        file_index=file_index,
        session_file_factory=lambda user, conversation_id: SessionFileEvidenceRetriever(
            file_index, user, conversation_id
        ),
        capabilities={
            "model": {"status": "ready" if model_ready else "unavailable"},
            "knowledge": {
                "status": "ready" if knowledge_ready else "unavailable"
            },
            "web": {"status": "ready" if web_ready else "unavailable"},
            "session_file": {
                "status": "ready" if session_file_ready else "unavailable"
            },
        },
    )
