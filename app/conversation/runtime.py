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
_MAX_QUOTE = 800
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


class ModelPlannerAdapter:
    _SYSTEM_PROMPT = (
        "你是有界研究规划器。只返回 JSON 对象，不调用任何工具，不委派任务。"
        "字段必须为 objective、subquestions、knowledge_queries、web_queries。"
        "最多生成 3 个子问题、2 个知识库查询和 3 个网络查询。"
        "当本轮关闭 Web 时，web_queries 必须为空。"
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
                {"role": "system", "content": self._SYSTEM_PROMPT},
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
            return TurnResearchPlan(
                objective=payload["objective"],
                subquestions=tuple(payload.get("subquestions", ())),
                knowledge_queries=tuple(payload.get("knowledge_queries", ())),
                web_queries=(
                    tuple(payload.get("web_queries", ())) if turn.use_web else ()
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
                    "content": (
                        "你是一次性覆盖审阅器。仅返回 JSON，字段为 "
                        "uncovered_questions、"
                        "knowledge_queries、web_queries。只针对未覆盖问题生成补充查询；"
                        "每个未覆盖问题对每个来源最多一个查询，不重复已有查询。"
                        "recent_history 为此前数轮问答摘录；已在其中确立的事实"
                        "不要再当作未覆盖问题。"
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
                    "content": (
                        "你是引用式回答综合器。仅返回 JSON，字段为 "
                        "answer_sections、claims、"
                        "limitations。每个 answer_sections 项含 text 和 claim_indexes；"
                        "claims 项含 statement 和 evidence_ids。只使用给出的证据 ID。"
                        "用自然中文段落直接回答问题，不复述内部结构。"
                        "recent_history 为此前数轮问答摘录；回答需自然衔接其中"
                        "已确立的概念与结论，避免重复解释。回答控制在约 "
                        f"{answer_budget} 个中文字符。涉及权限或安全限制时统一表述为"
                        "‘仅按允许列表执行’，不使用其他同义措辞。"
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


class KnowledgeEvidenceRetriever:
    def __init__(self, index: Any):
        self._index = index

    def search_sync(self, query: str, *, limit: int = 10) -> tuple[EvidenceItem, ...]:
        chunks = self._index.search(query, limit=min(10, limit))
        result: list[EvidenceItem] = []
        for chunk in chunks:
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
                )
            )
        return tuple(result)

    async def search(self, query: str, *, limit: int = 10) -> tuple[EvidenceItem, ...]:
        import asyncio

        return await asyncio.to_thread(self.search_sync, query, limit=limit)


class TavilyEvidenceRetriever:
    def __init__(self, provider: Any):
        self._provider = provider

    def search_sync(self, query: str, *, limit: int = 10) -> tuple[EvidenceItem, ...]:
        options = _web_search_options(query)
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
        for hit in result.hits[:5]:
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
                )
            )
        return tuple(items)

    async def search(self, query: str, *, limit: int = 10) -> tuple[EvidenceItem, ...]:
        import asyncio

        return await asyncio.to_thread(self.search_sync, query, limit=limit)


def _web_search_options(query: str) -> dict[str, str]:
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
    return ranked[0][1][:_MAX_QUOTE]


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
        return tuple(
            EvidenceItem(
                evidence_id=f"ev-file-{chunk.document_id}-{chunk.chunk_id}",
                source_kind="session_file",
                title=chunk.title,
                locator_kind="file",
                locator_value=f"{chunk.title}:{chunk.section_path or chunk.chunk_id}",
                quote=_relevant_excerpt(chunk.content, query),
            )
            for chunk in chunks
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

            web = TavilyEvidenceRetriever(TavilyWebProvider(settings.tavily_api_key))
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
