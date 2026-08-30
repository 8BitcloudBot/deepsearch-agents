"""Provider adapters for the bounded schema 5.0 conversation graph.

Adapters deliberately expose only short evidence snippets to the graph. Provider
SDKs and file parsers remain behind this module so the turn engine can be tested
without network or model credentials.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from app.conversation.contracts import EvidenceItem, TurnResearchPlan
from app.conversation.heuristics import is_deep_request as _is_deep_request
from app.conversation.output_schemas import (
    coerce_plan_output,
    coerce_review_output,
    coerce_synthesis_output,
)
from app.conversation.prompts import (
    COVERAGE_REVIEWER_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    TITLE_SYSTEM_PROMPT,
    synthesizer_system_prompt,
)
from app.conversation.turn import (
    CoverageDecision,
    SynthesisClaim,
    SynthesisDraft,
    SynthesisSection,
    TurnInput,
)
from app.logging_setup import (
    brief,
    configure_logging,
    log_model_usage,
)

_FENCE_RE = re.compile(
    r"^```(?:json)?\s*\n(?P<body>.*?)\n```$", re.DOTALL | re.IGNORECASE
)
logger = logging.getLogger("deepsearch.runtime")
# I4：短输出角色的 max_tokens 上限（真机实测 title 曾失控输出 2442 token）；
# synthesizer 不设限（回答 800～1400 汉字需要空间）。
_MAX_TOKENS_TITLE = 200
_MAX_TOKENS_PLANNER = 600
_MAX_TOKENS_REVIEWER = 800


def _bind_max_tokens(model: Any, max_tokens: int) -> Any:
    if callable(getattr(model, "bind", None)):
        return model.bind(max_tokens=max_tokens)
    return model
_MAX_QUOTE = 2000
_EXCERPT_PARAGRAPHS = 2  # 每次摘录取查询词密度最高的前 N 个段落
_MAX_WEB_HITS_PER_QUERY = 5  # 每条 web 查询交付证据数上限（providers 层有同值兜底）
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


def _normalize_limitation(item: Any) -> str:
    """模型可能把 limitation 返回成 {type, detail} 等对象。

    提取常见可读字段而不是让用户看到 Python repr；未知形状退化为
    ensure_ascii=False 的 JSON 串，仍可读且无转义噪声。
    """
    if isinstance(item, Mapping):
        for key in ("detail", "text", "message", "reason"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        try:
            return json.dumps(item, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(item)
    return str(item).strip()


def _strict_json(response: Any) -> dict[str, Any]:
    raw = _response_text(response)
    match = _FENCE_RE.fullmatch(raw)
    if match:
        raw = match.group("body").strip()
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        # 围栏之外的说明性前后缀噪声：取首个 { 到最后一个 } 的窗口再试一次，
        # 避免"模型夹带了句解释文字"导致整轮失败。
        start, end = raw.find("{"), raw.rfind("}")
        if not 0 <= start < end:
            raise ValueError("model response is invalid") from None
        try:
            payload = json.loads(raw[start : end + 1])
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError("model response is invalid") from exc
    if not isinstance(payload, dict):
        raise ValueError("model response is invalid")
    return payload


def _history_records(turn: TurnInput) -> list[dict[str, str]]:
    return [
        {"question": question, "answer": answer}
        for question, answer in turn.recent_history
    ]


def _history_brief(turn: TurnInput) -> list[dict[str, str]]:
    """审阅器专用历史摘要（H12）：问答各截前 200/300 字符。

    审阅器只需判断"哪些事实已确立"，无需逐字全量历史；
    planner/synthesizer 保持全量。
    """
    return [
        {"question": question[:200], "answer": answer[:300]}
        for question, answer in turn.recent_history
    ]


def _current_date_line(now: Any = None) -> str:
    """组装期注入当前日期（ISO + 星期），供所有角色 system prompt 头部使用。

    使用服务器本地时区（G7）：UTC 在 UTC+8 场景下每天 0-8 点会注入前一日。
    """
    import datetime as dt

    moment = now or dt.datetime.now().astimezone()
    weekdays = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")
    iso = moment.date().isoformat()
    weekday = weekdays[moment.weekday()]
    return f"今天是{iso}（{weekday}）。"


class ModelPlannerAdapter:
    _SYSTEM_PROMPT = PLANNER_SYSTEM_PROMPT

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
        self._model = _bind_max_tokens(planner_model, _MAX_TOKENS_PLANNER)

    async def plan(self, turn: TurnInput) -> TurnResearchPlan:
        response = await self._model.ainvoke(
            [
                {
                    "role": "system",
                    "content": _current_date_line() + "\n" + PLANNER_SYSTEM_PROMPT,
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
        log_model_usage(logger, "planner", response)
        payload = _strict_json(response)
        payload = coerce_plan_output(payload)
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
        self._model = _bind_max_tokens(model, _MAX_TOKENS_REVIEWER)

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
                    + COVERAGE_REVIEWER_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": turn.question,
                            "use_web": turn.use_web,
                            "recent_history": _history_brief(turn),
                            "plan": plan.as_dict(),
                            "evidence": evidence,
                            "limitations": list(limitations),
                        },
                        ensure_ascii=False,
                    ),
                },
            ]
        )
        log_model_usage(logger, "coverage-reviewer", response)
        payload = _strict_json(response)
        payload = coerce_review_output(payload)
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
    def __init__(self, model: Any, streamed: bool = False):
        self._model = model
        self._streamed = streamed

    async def synthesize(
        self,
        turn: TurnInput,
        plan: TurnResearchPlan,
        evidence_items: tuple[EvidenceItem, ...],
        limitations: tuple[str, ...],
        *,
        on_delta: Any = None,
    ) -> SynthesisDraft:
        if self._streamed and on_delta is not None:
            try:
                return await self._synthesize_streamed(
                    turn, plan, evidence_items, limitations, on_delta
                )
            except Exception as exc:
                logger.warning("streamed synthesis failed, fallback: %s", brief(exc))
        return await self._synthesize_json(
            turn, plan, evidence_items, limitations
        )

    async def _synthesize_streamed(
        self,
        turn: TurnInput,
        plan: TurnResearchPlan,
        evidence_items: tuple[EvidenceItem, ...],
        limitations: tuple[str, ...],
        on_delta: Any,
    ) -> SynthesisDraft:
        """B1 方案A 两段式：先流式产出正文纯文本，再抽取 claims/limitations。

        正文经 on_delta 增量透传（前端实时渲染）；第二次调用把 claim
        statement 锚回正文原句并挂证据 ID，构造与 JSON 路径同形的
        SynthesisDraft，finalize 的引用编号/证据交运算全部复用。
        任一步失败抛给上层回退 JSON 路径。
        """
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
        # 长度预算信号与引擎一致（G7）
        if plan.research_intensity in ("standard", "deep"):
            deep = plan.research_intensity == "deep"
        else:
            deep = _is_deep_request(turn.question)
        answer_budget = "800～1400" if deep else "400～800"

        prose_messages = [
            {
                "role": "system",
                "content": _current_date_line()
                + "\n"
                + synthesizer_system_prompt(answer_budget)
                + "\n\n本次输出为纯文本正文：用自然中文分段撰写（段落间用空行分隔），"
                "不要输出 JSON，不要输出字段名或任何结构标记；"
                "每段聚焦一个要点；不得引用任何证据编号。",
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": turn.question,
                        "recent_history": _history_records(turn),
                        "prior_summary": turn.prior_summary,
                        "plan": plan.as_dict(),
                        "evidence": evidence,
                        "limitations": list(limitations),
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        chunks: list[str] = []
        async for chunk in self._model.astream(prose_messages):
            piece = getattr(chunk, "content", chunk)
            if isinstance(piece, list):
                piece = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in piece
                )
            if not isinstance(piece, str) or not piece:
                continue
            chunks.append(piece)
            on_delta(piece)
        prose = "".join(chunks).strip()
        if not prose:
            raise ValueError("model response is invalid")

        extraction = await self._model.ainvoke(
            [
                {
                    "role": "system",
                    "content": (
                        "你是引用抽取器。给定回答正文与证据列表，"
                        "从正文中挑选每个依赖证据的事实句（statement 必须是正文原句的连续子串），"
                        "并标注其依据的证据 ID。仅返回 JSON："
                        '{"claims": [{"statement": "...", "evidence_ids": ["..."]}], '
                        '"limitations": ["..."]}。'
                        "evidence_ids 只能使用给定证据的 evidence_id；"
                        "无对应证据的句子不要挑。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"answer": prose, "evidence": evidence},
                        ensure_ascii=False,
                    ),
                },
            ]
        )
        log_model_usage(logger, "synthesizer-extract", extraction)
        raw = _strict_json(extraction)
        raw_claims = raw.get("claims")
        raw_limitations = raw.get("limitations", [])
        if not isinstance(raw_claims, list) or not isinstance(raw_limitations, list):
            raise ValueError("model response is invalid")

        sections_text = [part.strip() for part in prose.split("\n\n") if part.strip()]
        claims: list[SynthesisClaim] = []
        for item in raw_claims:
            if not isinstance(item, dict):
                continue
            statement = str(item.get("statement", "")).strip()
            evidence_ids = tuple(
                eid
                for eid in (item.get("evidence_ids") or [])
                if isinstance(eid, str)
            )
            if statement and evidence_ids:
                claims.append(SynthesisClaim(statement, evidence_ids))

        sections = []
        for text in sections_text:
            indexes = tuple(
                index
                for index, claim in enumerate(claims)
                if claim.statement in text
            )
            sections.append(SynthesisSection(text, indexes))
        if not sections:
            raise ValueError("model response is invalid")
        return SynthesisDraft(
            tuple(sections),
            tuple(claims),
            tuple(_normalize_limitation(item) for item in raw_limitations),
        )

    async def _synthesize_json(
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
        # 长度预算信号与引擎一致：规划器 research_intensity 优先，缺失时
        # 回退关键词启发（G7 修复两处信号可能不一致导致预算错档）。
        if plan.research_intensity in ("standard", "deep"):
            deep = plan.research_intensity == "deep"
        else:
            deep = _is_deep_request(turn.question)
        answer_budget = "800～1400" if deep else "400～800"
        response = await self._model.ainvoke(
            [
                {
                    "role": "system",
                    "content": _current_date_line()
                    + "\n"
                    + synthesizer_system_prompt(answer_budget),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": turn.question,
                            "recent_history": _history_records(turn),
                            "prior_summary": turn.prior_summary,
                            "plan": plan.as_dict(),
                            "evidence": evidence,
                            "limitations": list(limitations),
                        },
                        ensure_ascii=False,
                    ),
                },
            ]
        )
        log_model_usage(logger, "synthesizer", response)
        payload = _strict_json(response)
        payload = coerce_synthesis_output(payload)
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
                sections, claims, tuple(_normalize_limitation(item) for item in raw_limitations)
            )
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise ValueError("model response is invalid") from exc


class ModelTitleAdapter:
    """B10-1：首问生成会话标题；任何失败由调用方回退正则路径。"""

    def __init__(self, model: Any):
        self._model = _bind_max_tokens(model, _MAX_TOKENS_TITLE)

    async def generate(self, question: str) -> str:
        response = await self._model.ainvoke(
            [
                {
                    "role": "system",
                    "content": _current_date_line() + "\n" + TITLE_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"question": question}, ensure_ascii=False
                    ),
                },
            ]
        )
        log_model_usage(logger, "title", response)
        payload = _strict_json(response)
        title = str(payload.get("title", "")).strip()
        if not title:
            raise ValueError("model response is invalid")
        return title[:36]


def _normalized_scores(values: list[float]) -> list[float]:
    """Clamp provider scores into [0, 1]; rank-style scales (>1) use batch max."""
    if not values:
        return []
    maximum = max(values)
    if maximum > 1:
        return [max(value, 0.0) / maximum for value in values]
    return [min(max(value, 0.0), 1.0) for value in values]


def _rank_decay_scores(count: int) -> list[float]:
    from app.conversation.heuristics import rank_decay_scores

    return rank_decay_scores(count)


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
        hits = result.hits[:_MAX_WEB_HITS_PER_QUERY]
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
                published_at=getattr(hit, "published_date", None),
            )
            )
        return tuple(items)

    async def search(self, query: str, *, limit: int = 10) -> tuple[EvidenceItem, ...]:
        import asyncio

        return await asyncio.to_thread(self.search_sync, query, limit=limit)


def _keyword_search_options(query: str) -> dict[str, str]:
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


def _web_search_options(query: str, plan: Any = None) -> dict[str, str]:
    """规划器 search_hints 优先；未提供的键由关键词启发补齐（C3）。

    合并语义保证规划器只给 time_range 等部分 hints 时，时效判定
    （topic=news + time_range=month）不丢失。
    """
    fallback = _keyword_search_options(query)
    if plan is not None and getattr(plan, "search_hints", None):
        options = dict(fallback)
        for key in ("search_depth", "topic", "time_range"):
            value = plan.hint(key)
            if isinstance(value, str) and value.strip():
                options[key] = value.strip()
        return options
    return fallback


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


class UserKnowledgeRetriever:
    """当前用户个人知识库（RAG 入库 collection）的检索适配器。

    与 KnowledgeEvidenceRetriever 同构：source_kind 仍为 knowledge，
    引擎把其结果并入同一分支评分排序；分库物理隔离保证用户间不可见。
    """

    def __init__(self, index: Any):
        self._index = index

    def search_sync(self, query: str, *, limit: int = 10) -> tuple[EvidenceItem, ...]:
        chunks = self._index.search(query, limit=min(10, limit))
        scores = _normalized_scores([chunk.score for chunk in chunks])
        result: list[EvidenceItem] = []
        for chunk, score in zip(chunks, scores):
            safe_key = re.sub(r"[^A-Za-z0-9_.:-]+", "-", chunk.chunk_id)
            result.append(
                EvidenceItem(
                    evidence_id=f"ev-knowledge-{chunk.document_id}-{safe_key}",
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


def _with_temperature(model: Any, temperature: float | None) -> Any:
    """H10：按角色温度覆写；未设置时原样共享同一模型实例。"""
    if temperature is None:
        return model
    if callable(getattr(model, "model_copy", None)):
        return model.model_copy(update={"temperature": temperature})
    return model


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

    configure_logging(environ)
    settings = ConversationSettings.from_env(environ)
    store = ConversationStore(store_path)
    report = ConversationReport(report_root, store)
    removed = report.purge_orphans()
    if removed:
        logger.info("purged %d orphaned report director(ies)", removed)

    planner: Any = _UnavailablePlanner()
    synthesizer: Any = _UnavailableSynthesizer()
    title_generator: Any = None
    model_ready = False
    if settings.model_api_key:
        try:
            from app.conversation.model import build_agent_model

            base_model, _ = build_agent_model(settings)
            # 分级模型路由（B2 建议）：规划/审阅/标题为小输出任务，
            # MODEL_NAME_LIGHT 配置时路由到便宜快速模型，综合器保持主模型。
            if settings.model_name_light:
                light_model, _ = build_agent_model(
                    settings, model_name_override=settings.model_name_light
                )
            else:
                light_model = base_model
            planner = ModelPlannerAdapter(
                _with_temperature(light_model, settings.model_temperature_planner)
            )
            synthesizer = ModelSynthesizerAdapter(
                _with_temperature(base_model, settings.model_temperature_synthesizer),
                streamed=settings.model_streamed_synthesis,
            )
            coverage_reviewer = ModelCoverageReviewerAdapter(
                _with_temperature(light_model, settings.model_temperature_reviewer)
            )
            title_generator = ModelTitleAdapter(light_model)
            model_ready = True
        except Exception as exc:
            logger.warning("research model unavailable: %s", brief(exc))
            planner = _UnavailablePlanner()
            synthesizer = _UnavailableSynthesizer()
            coverage_reviewer = None
            title_generator = None
    else:
        coverage_reviewer = None

    # embedder 独立构造（构造本身 lazy 不加载模型）：主库索引 readiness
    # 失败不得连带剥夺个人知识库的可用性。
    embedder: Any = None
    try:
        from app.knowledge.embeddings import FastEmbedEmbeddingAdapter

        embedder = FastEmbedEmbeddingAdapter(
            model=settings.knowledge.embedding_model,
            version=settings.knowledge.embedding_version,
            dimension=settings.knowledge.embedding_dimension,
            cache_dir=str(runtime_root / ".cache" / "fastembed"),
        )
    except Exception as exc:
        logger.warning("embedding adapter unavailable: %s", brief(exc))

    knowledge: Any = _UnavailableRetriever()
    knowledge_ready = False
    try:
        from app.knowledge.contracts import (
            KnowledgeIndexSpec,
            resolve_knowledge_index_path,
        )
        from app.knowledge.qdrant_local import QdrantLocalKnowledgeIndex

        spec = KnowledgeIndexSpec(
            collection_id=settings.knowledge.collection,
            embedding=embedder.descriptor,
            distance="cosine",
            chunking_version="semantic-markdown-v1",
        )
        index_path = resolve_knowledge_index_path(
            settings.knowledge.index_path, runtime_root=runtime_root
        )
        ready, reason = QdrantLocalKnowledgeIndex.check_readiness(index_path, spec)
        if ready and embedder is not None:
            knowledge = KnowledgeEvidenceRetriever(
                QdrantLocalKnowledgeIndex(
                    index_path, spec, embedder, min_score=settings.knowledge.min_score
                )
            )
            knowledge_ready = True
        else:
            logger.warning("knowledge index not ready: %s", reason)
    except Exception as exc:
        knowledge = _UnavailableRetriever()
        logger.warning("knowledge index unavailable: %s", brief(exc))

    # 个人知识库（RAG 入库）装配：独立 per-user collection，
    # 装配失败不拖垮主链路（fail-safe 降级为无个人库）。
    upload_store: Any = None
    try:
        if embedder is not None:
            from app.conversation.uploads import UploadKnowledgeStore

            upload_store = UploadKnowledgeStore(
                runtime_root / ".data" / "user-uploads",
                embedder,
                min_score=settings.knowledge.min_score,
            )
    except Exception as exc:
        upload_store = None
        logger.warning("personal knowledge store unavailable: %s", brief(exc))

    web: Any = _UnavailableRetriever()
    web_ready = False
    if settings.tavily_api_key:
        try:
            from app.providers.tavily import TavilyWebProvider

            web = TavilyEvidenceRetriever(
                TavilyWebProvider(settings.tavily_api_key)
            )
            web_ready = True
        except Exception as exc:
            logger.warning("web provider unavailable: %s", brief(exc))
            web = _UnavailableRetriever()

    logger.info(
        "conversation application assembled: model=%s knowledge=%s web=%s uploads=%s",
        "ready" if model_ready else "unavailable",
        "ready" if knowledge_ready else "unavailable",
        "ready" if web_ready else "unavailable",
        "ready" if upload_store is not None else "unavailable",
    )
    engine = TurnResearchEngine(
        planner,
        knowledge,
        web,
        synthesizer,
        coverage_reviewer,
        citation_validation=settings.enable_citation_validation,
        streamed_synthesis=settings.model_streamed_synthesis,
    )
    return ConversationApplication(
        store,
        engine,
        report,
        capabilities={
            "model": {"status": "ready" if model_ready else "unavailable"},
            "knowledge": {
                "status": "ready" if knowledge_ready else "unavailable"
            },
            "web": {"status": "ready" if web_ready else "unavailable"},
            # 会话附件路径已由知识库入库方案取代（T1）；键保留维持 WS 合同稳定
            "session_file": {"status": "unavailable"},
        },
        upload_store=upload_store,
        stale_turn_seconds=settings.turn_stale_seconds,
        max_turns_per_conversation=settings.max_turns_per_conversation,
        title_generator=title_generator,
        history_token_budget=settings.history_token_budget,
    )
