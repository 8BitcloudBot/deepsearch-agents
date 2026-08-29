"""Bounded LangGraph turn orchestration for the conversation product."""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from dataclasses import dataclass, replace
from functools import partial
from typing import Any, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph

from app.conversation.contracts import (
    SCHEMA_VERSION,
    Claim,
    EvidenceItem,
    TurnResearchPlan,
    TurnResult,
)
from app.conversation.heuristics import is_deep_request as _is_deep_request
from app.logging_setup import brief

logger = logging.getLogger("deepsearch.turn")


@dataclass(frozen=True)
class TurnInput:
    question: str
    use_web: bool
    attachment_ids: tuple[str, ...]
    recent_history: tuple[tuple[str, str], ...]
    uncovered_questions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.question, str) or not self.question.strip():
            raise ValueError("question must be non-empty")
        if type(self.use_web) is not bool:
            raise ValueError("use_web must be boolean")
        if len(self.recent_history) > 6:
            raise ValueError("recent history is limited to six turns")
        if len(self.uncovered_questions) > 3:
            raise ValueError("uncovered questions are limited to three")


@dataclass(frozen=True)
class CoverageDecision:
    """Validated, single-round coverage review output."""

    uncovered_questions: tuple[str, ...] = ()
    knowledge_queries: tuple[str, ...] = ()
    web_queries: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field, maximum in (
            ("uncovered_questions", 3),
            ("knowledge_queries", 3),
            ("web_queries", 3),
        ):
            values = getattr(self, field)
            if not isinstance(values, tuple) or len(values) > maximum:
                raise ValueError(f"{field} exceed the allowed limit")
            cleaned = tuple(
                value.strip()
                for value in values
                if isinstance(value, str) and value.strip()
            )
            if len(cleaned) != len(set(value.casefold() for value in cleaned)):
                raise ValueError(f"{field} contain duplicates")
            object.__setattr__(self, field, cleaned)


@dataclass(frozen=True)
class QueryOutcome:
    """Non-sensitive retrieval telemetry used by the coverage fast path."""

    source_kind: str
    query_index: int
    hit_count: int


@dataclass(frozen=True)
class SynthesisClaim:
    statement: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class SynthesisSection:
    text: str
    claim_indexes: tuple[int, ...]


@dataclass(frozen=True)
class SynthesisDraft:
    sections: tuple[SynthesisSection, ...]
    claims: tuple[SynthesisClaim, ...]
    limitations: tuple[str, ...]


class TurnExecutionError(RuntimeError):
    """Safe terminal failure for one turn."""


class TurnPlanner(Protocol):
    async def plan(self, turn: TurnInput) -> TurnResearchPlan: ...


class EvidenceRetriever(Protocol):
    async def search(
        self, query: str, *, limit: int = 10
    ) -> tuple[EvidenceItem, ...]: ...


class TurnSynthesizer(Protocol):
    async def synthesize(
        self,
        turn: TurnInput,
        plan: TurnResearchPlan,
        evidence_items: tuple[EvidenceItem, ...],
        limitations: tuple[str, ...],
    ) -> SynthesisDraft: ...


class CoverageReviewer(Protocol):
    async def review(
        self,
        turn: TurnInput,
        plan: TurnResearchPlan,
        evidence_items: tuple[EvidenceItem, ...],
        limitations: tuple[str, ...],
    ) -> CoverageDecision: ...


class _TurnState(TypedDict):
    turn: TurnInput
    plan: TurnResearchPlan | None
    knowledge: tuple[EvidenceItem, ...]
    web: tuple[EvidenceItem, ...]
    query_outcomes: tuple[QueryOutcome, ...]
    limitations: tuple[str, ...]
    coverage: CoverageDecision | None
    result: TurnResult | None
    supplemental_rounds: int
    supplemental_used: int
    executed_queries: tuple[str, ...]
    user_knowledge_retriever: Any


def _plan_is_deep(plan: TurnResearchPlan | None, question: str) -> bool:
    """规划器 research_intensity 字段优先，缺失/解析失败时回退关键词启发。"""
    if plan is not None and plan.research_intensity is not None:
        return plan.research_intensity == "deep"
    return _is_deep_request(question)


def _route_after_review(state: _TurnState) -> str:
    coverage = state.get("coverage")
    if not coverage or not (coverage.knowledge_queries or coverage.web_queries):
        return "synthesize"
    if state.get("supplemental_rounds", 0) >= _MAX_SUPPLEMENTAL_ROUNDS:
        return "synthesize"
    return "supplemental"


class TurnResearchEngine:
    """Runs a deterministic graph while keeping provider adapters replaceable."""

    def __init__(
        self,
        planner: TurnPlanner,
        knowledge: EvidenceRetriever,
        web: EvidenceRetriever,
        synthesizer: TurnSynthesizer,
        coverage_reviewer: CoverageReviewer | None = None,
        *,
        citation_validation: bool = False,
    ) -> None:
        self._planner = planner
        self._knowledge = knowledge
        self._web = web
        self._synthesizer = synthesizer
        self._coverage_reviewer = coverage_reviewer
        self._citation_validation = citation_validation
        graph = StateGraph(_TurnState)
        graph.add_node("plan", self._plan)
        graph.add_node("retrieve", self._retrieve_initial)
        graph.add_node("review", self._review_coverage)
        graph.add_node("supplemental", self._retrieve_supplemental)
        graph.add_node(
            "synthesize",
            partial(
                self._synthesize,
                citation_validation=self._citation_validation,
            ),
        )
        graph.add_edge(START, "plan")
        graph.add_edge("plan", "retrieve")
        graph.add_edge("retrieve", "review")
        graph.add_conditional_edges(
            "review",
            _route_after_review,
            {"supplemental": "supplemental", "synthesize": "synthesize"},
        )
        # 补充检索回环：supplemental 执行新查询后回到 review 复评，
        # 由轮次上限与查询总预算保证收敛（retrieve 是首轮计划查询节点，
        # 回边到它会让每一轮重复执行初始查询，故复用 review 生成下一轮）。
        graph.add_edge("supplemental", "review")
        graph.add_edge("synthesize", END)
        self._graph = graph.compile()

    async def run(
        self,
        turn: TurnInput,
        *,
        user_knowledge: EvidenceRetriever | None = None,
    ) -> TurnResult:
        """user_knowledge：当前用户的个人知识库检索器（知识库入库方案）。

        其结果并入 knowledge 来源分支统一评分排序，DAG 形状不变。
        """
        return await self._run(turn, user_knowledge=user_knowledge)

    async def _run(
        self,
        turn: TurnInput,
        *,
        user_knowledge: EvidenceRetriever | None = None,
    ) -> TurnResult:
        state = await self._graph.ainvoke(
            {
                "turn": turn,
                "plan": None,
                "knowledge": (),
                "web": (),
                "query_outcomes": (),
                "limitations": (),
                "coverage": None,
                "result": None,
                "supplemental_rounds": 0,
                "supplemental_used": 0,
                "executed_queries": (),
                "user_knowledge_retriever": user_knowledge,
            },
            # plan+retrieve + (review+supplemental)×(MAX_ROUNDS+1) + synthesize
            # 的安全上限；轮次上限保证正常收敛，这里只兜异常路径。
            config={"recursion_limit": 5 + 2 * (_MAX_SUPPLEMENTAL_ROUNDS + 1) + 3},
        )
        result = state.get("result")
        if not isinstance(result, TurnResult):
            raise TurnExecutionError("model-response-invalid")
        return result

    async def _plan(self, state: _TurnState) -> dict[str, object]:
        logger.debug("node=plan enter")
        try:
            plan = await self._planner.plan(state["turn"])
        except Exception as exc:
            logger.warning("planner failed: %s", brief(exc))
            raise TurnExecutionError("model-response-invalid") from exc
        logger.debug("node=plan exit intensity=%s", plan.research_intensity)
        return {"plan": plan}

    async def _retrieve_initial(self, state: _TurnState) -> dict[str, object]:
        logger.debug("node=retrieve enter")
        plan = self._require_plan(state)
        turn = state["turn"]
        deep = _plan_is_deep(plan, turn.question)
        knowledge_queries = (plan.knowledge_queries or (turn.question,))[:2]
        web_queries = (
            (plan.web_queries or (turn.question,))[: 3 if deep else 2]
            if turn.use_web
            else ()
        )
        async def retrieve_knowledge() -> list[tuple[str, int, object]]:
            # 主库与当前用户个人知识库"库间并行、库内串行"发同一组查询
            # （Qdrant local 不支持并发访问）；结果合并进 knowledge 分支统一评分。
            queries = knowledge_queries

            async def one_library(
                retriever: Any, index_offset: int
            ) -> list[tuple[str, int, object]]:
                records: list[tuple[str, int, object]] = []
                for offset, query in enumerate(queries):
                    try:
                        result: object = await retriever.search(query, limit=10)
                    except Exception as exc:
                        result = exc
                    records.append(("knowledge", index_offset + offset, result))
                return records

            extra = state.get("user_knowledge_retriever")
            main_task = one_library(self._knowledge, 0)
            if extra is None:
                return await main_task
            main_records, extra_records = await asyncio.gather(
                main_task, one_library(extra, len(queries))
            )
            return [*main_records, *extra_records]

        async def retrieve_web() -> list[tuple[str, int, object]]:
            results = await asyncio.gather(
                *(self._web.search(query, limit=10) for query in web_queries),
                return_exceptions=True,
            )
            return [
                ("web", index, result) for index, result in enumerate(results)
            ]

        batches = await asyncio.gather(retrieve_knowledge(), retrieve_web())
        records = [record for batch in batches for record in batch]
        grouped: dict[str, list[EvidenceItem]] = {
            "knowledge": [],
            "web": [],
        }
        outcomes: list[QueryOutcome] = []
        limitations = list(state["limitations"])
        failed_sources: set[str] = set()
        successful_sources: set[str] = set()
        limitation_labels = {
            "knowledge": "本地知识库检索暂不可用。",
            "web": "实时网络检索暂不可用。",
        }
        for source_kind, query_index, result in records:
            if isinstance(result, Exception):
                failed_sources.add(source_kind)
                outcomes.append(QueryOutcome(source_kind, query_index, 0))
                continue
            items = tuple(result)
            successful_sources.add(source_kind)
            grouped[source_kind].extend(items)
            outcomes.append(QueryOutcome(source_kind, query_index, len(items)))
        partial_labels = {
            "knowledge": "本地知识库部分检索未完成。",
            "web": "实时网络部分检索未完成。",
        }
        for source in ("knowledge", "web"):
            if source not in failed_sources:
                continue
            limitations.append(
                partial_labels[source]
                if source in successful_sources
                else limitation_labels[source]
            )
        logger.debug(
            "node=retrieve exit knowledge=%d web=%d failed=%s",
            len(grouped["knowledge"]),
            len(grouped["web"]),
            sorted(failed_sources) or "none",
        )
        return {
            "knowledge": tuple(grouped["knowledge"]),
            "web": _apply_global_rank_decay(tuple(grouped["web"])),
            "query_outcomes": tuple(outcomes),
            "limitations": tuple(dict.fromkeys(limitations)),
        }

    async def _review_coverage(self, state: _TurnState) -> dict[str, object]:
        logger.debug("node=review enter rounds=%d", state.get("supplemental_rounds", 0))
        if self._coverage_reviewer is None:
            return {"coverage": CoverageDecision()}
        plan = self._require_plan(state)
        # 命中数≠真答了问题，伪覆盖场景（证据多但无关）由审阅器兜底把关，
        # 不再走"每来源有命中即跳过审阅"的捷径（B8）。
        plan = self._require_plan(state)
        turn = state["turn"]
        deep = _plan_is_deep(plan, turn.question)
        evidence_limit = 8 if deep else 6
        evidence_items = _select_evidence(
            state["knowledge"],
            (),  # session_file 源已由知识库入库方案取代；形参保留兼容历史签名
            state["web"],
            limit=evidence_limit,
        )
        evidence_items = _limit_quotes(
            evidence_items,
            limit=(
                _EVIDENCE_QUOTE_DEEP_LIMIT
                if evidence_limit == 8
                else _EVIDENCE_QUOTE_STANDARD_LIMIT
            ),
        )
        try:
            decision = await self._coverage_reviewer.review(
                state["turn"], plan, evidence_items, state["limitations"]
            )
            if not isinstance(decision, CoverageDecision):
                raise ValueError
        except Exception:
            return {
                "coverage": CoverageDecision(),
                "limitations": (*state["limitations"], "覆盖审阅暂不可用。"),
            }

        executed = {
            query.casefold()
            for query in (
                *state.get("executed_queries", ()),
                *(plan.knowledge_queries or (state["turn"].question,)),
                *(
                    plan.web_queries or (state["turn"].question,)
                    if state["turn"].use_web
                    else ()
                ),
            )
        }
        knowledge_queries = _new_queries(decision.knowledge_queries, executed)
        web_queries = _new_queries(decision.web_queries, executed)
        # 补充查询跨轮记账：总预算内每轮至多 _SUPPLEMENTAL_PER_ROUND_LIMIT 条；
        # 无新查询时返回空 decision，路由自然退出回环。
        remaining = max(
            0,
            _MAX_SUPPLEMENTAL_QUERIES_TOTAL - state.get("supplemental_used", 0),
        )
        per_round = min(_SUPPLEMENTAL_PER_ROUND_LIMIT, remaining)
        candidates = [
            ("knowledge", query) for query in knowledge_queries[:1]
        ] + [
            ("web", query) for query in web_queries[:1] if state["turn"].use_web
        ]
        bounded_knowledge = tuple(
            query for source, query in candidates[:per_round] if source == "knowledge"
        )
        bounded_web = tuple(
            query for source, query in candidates[:per_round] if source == "web"
        )
        bounded = CoverageDecision(
            uncovered_questions=decision.uncovered_questions,
            knowledge_queries=bounded_knowledge,
            web_queries=bounded_web,
        )
        turn = replace(state["turn"], uncovered_questions=bounded.uncovered_questions)
        # 多轮回环时逐轮累积会产生数条相似文案，收敛为仅保留最新一轮
        limitations = [
            item for item in state["limitations"] if not item.startswith("未覆盖问题：")
        ]
        if bounded.uncovered_questions:
            limitations.append("未覆盖问题：" + "；".join(bounded.uncovered_questions))
        if state.get("supplemental_rounds", 0) >= _MAX_SUPPLEMENTAL_ROUNDS and (
            bounded.uncovered_questions
        ):
            limitations.append("补充检索预算已用尽，仍有问题未被证据覆盖。")
        issued = (*bounded_knowledge, *bounded_web)
        logger.debug(
            "node=review exit uncovered=%d queries=%d round=%d/%d",
            len(bounded.uncovered_questions),
            len(issued),
            state.get("supplemental_rounds", 0),
            _MAX_SUPPLEMENTAL_ROUNDS,
        )
        return {
            "coverage": bounded,
            "turn": turn,
            "limitations": tuple(dict.fromkeys(limitations)),
            "executed_queries": (
                *state.get("executed_queries", ()),
                *issued,
            ),
            "supplemental_used": state.get("supplemental_used", 0) + len(issued),
        }

    async def _retrieve_supplemental(self, state: _TurnState) -> dict[str, object]:
        logger.debug("node=supplemental enter")
        coverage = state.get("coverage") or CoverageDecision()
        knowledge = list(state["knowledge"])
        web = list(state["web"])
        limitations = list(state["limitations"])
        tasks = [
            self._knowledge.search(query, limit=10)
            for query in coverage.knowledge_queries
        ] + [
            self._web.search(query, limit=10)
            for query in coverage.web_queries
            if state["turn"].use_web
        ]
        sources = ["knowledge"] * len(coverage.knowledge_queries) + [
            "web"
        ] * len(coverage.web_queries if state["turn"].use_web else ())
        results = await asyncio.gather(*tasks, return_exceptions=True)
        failed = False
        for source, result in zip(sources, results, strict=True):
            if isinstance(result, BaseException):
                failed = True
            elif source == "knowledge":
                knowledge.extend(result)
            else:
                web.extend(result)
        if failed:
            limitations.append("补充检索暂不可用。")
        # 旧+新全量重编：补充轮证据接在已有位次之后，避免再次冒出并列 1.0
        logger.debug(
            "node=supplemental exit knowledge=%d web=%d round=%d",
            len(knowledge),
            len(web),
            state.get("supplemental_rounds", 0) + 1,
        )
        return {
            "knowledge": tuple(knowledge),
            "web": _apply_global_rank_decay(
                (*state.get("web", ()), *web)
            ),
            "limitations": tuple(dict.fromkeys(limitations)),
            "supplemental_rounds": state.get("supplemental_rounds", 0) + 1,
        }

    async def _synthesize(
        self,
        state: _TurnState,
        *,
        citation_validation: bool = False,
        resynthesis_hint: str | None = None,
    ) -> dict[str, object]:
        plan = self._require_plan(state)
        evidence_limit = 8 if _plan_is_deep(plan, state["turn"].question) else 6
        evidence_items = _select_evidence(
            state["knowledge"],
            (),  # session_file 源已由知识库入库方案取代；形参保留兼容历史签名
            state["web"],
            limit=evidence_limit,
        )
        evidence_items = _limit_quotes(
            evidence_items,
            limit=(
                _EVIDENCE_QUOTE_DEEP_LIMIT
                if evidence_limit == 8
                else _EVIDENCE_QUOTE_STANDARD_LIMIT
            ),
        )
        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                draft = await self._synthesizer.synthesize(
                    state["turn"], plan, evidence_items, state["limitations"]
                )
                logger.debug(
                    "node=synthesize exit sections=%d claims=%d",
                    len(draft.sections),
                    len(draft.claims),
                )
                if citation_validation:
                    return {
                        "result": _finalize_draft_with_validation(
                            draft,
                            evidence_items,
                            state["limitations"],
                            hint=resynthesis_hint,
                        )
                    }
                return {
                    "result": _finalize_draft(
                        draft, evidence_items, state["limitations"]
                    )
                }
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "synthesis attempt %d failed: %s", _attempt + 1, brief(exc)
                )
        if isinstance(last_error, TurnExecutionError):
            raise last_error
        raise TurnExecutionError("model-response-invalid") from last_error

    @staticmethod
    def _require_plan(state: _TurnState) -> TurnResearchPlan:
        plan = state["plan"]
        if not isinstance(plan, TurnResearchPlan):
            raise TurnExecutionError("model-response-invalid")
        return plan


_SOURCE_ORDER = ("knowledge", "session_file", "web")

# ---- 规模常量区（B5/B6 调参入口）----
_EVIDENCE_QUOTE_STANDARD_LIMIT = 1500  # 普通轮单条证据 quote 上限
_EVIDENCE_QUOTE_DEEP_LIMIT = 2000  # 深入轮单条证据 quote 上限
_EVIDENCE_TOTAL_CHAR_BUDGET = 24000  # 单轮证据总字符预算，超出按分数整条剔除
_MAX_SUPPLEMENTAL_ROUNDS = 3  # 补充检索最多轮数
_MAX_SUPPLEMENTAL_QUERIES_TOTAL = 6  # 跨轮补充查询总数预算
_SUPPLEMENTAL_PER_ROUND_LIMIT = 2  # 每轮补充查询数（延续原夹具）


def _enforce_total_budget(
    items: tuple[EvidenceItem, ...], *, budget: int = _EVIDENCE_TOTAL_CHAR_BUDGET
) -> tuple[EvidenceItem, ...]:
    """Drop whole lowest-score evidence items over the shared character budget."""
    used = 0
    result: list[EvidenceItem] = []
    for item in items:
        length = len(item.quote)
        if used + length > budget:
            continue
        result.append(item)
        used += length
    return tuple(result)


def _published_timestamp(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        from datetime import datetime

        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _apply_global_rank_decay(
    items: tuple[EvidenceItem, ...],
) -> tuple[EvidenceItem, ...]:
    """对 web 批次按合并后首现顺序统一重打 1/(i+1) 衰减分。

    各 web 查询独立检索时都从 1.0 起算，多查询合并后同位次并列、
    全局排序退化为插入序；此处按跨查询的唯一位次重编消除扎堆。
    knowledge 分数是 Qdrant 相关性真值，不得重编，保持原样。
    """
    result = list(items)
    seen: set[str] = set()
    position = 0
    for index, item in enumerate(result):
        if item.source_kind != "web" or item.evidence_id in seen:
            continue
        seen.add(item.evidence_id)
        result[index] = dataclasses.replace(item, score=1 / (position + 1))
        position += 1
    return tuple(result)


def _evidence_rank(item: EvidenceItem) -> tuple[float, float]:
    score = item.score if item.score is not None else 0.0
    return (-score, -_published_timestamp(item.published_at))


def _aggregate_by_locator(items: tuple[EvidenceItem, ...]) -> tuple[EvidenceItem, ...]:
    """Merge quotes that share one locator into a single longer evidence item."""
    buckets: dict[str, list[EvidenceItem]] = {}
    order: list[str] = []
    seen_ids: set[str] = set()
    for item in items:
        if item.evidence_id in seen_ids:
            continue
        seen_ids.add(item.evidence_id)
        key = f"{item.locator_kind}|{item.locator_value.casefold()}"
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(item)
    result: list[EvidenceItem] = []
    for key in order:
        members = buckets[key]
        best = max(members, key=_evidence_rank)
        if len(members) == 1:
            result.append(best)
            continue
        quotes: list[str] = []
        for member in sorted(members, key=_evidence_rank):
            for part in member.quote.split("\n"):
                cleaned = part.strip()
                if cleaned and cleaned not in quotes:
                    quotes.append(cleaned)
        merged = dataclasses.replace(best, quote="\n".join(quotes))
        result.append(merged)
    return tuple(result)


def _select_evidence(
    knowledge: tuple[EvidenceItem, ...],
    session_files: tuple[EvidenceItem, ...],
    web: tuple[EvidenceItem, ...],
    *,
    limit: int,
    char_budget: int = _EVIDENCE_TOTAL_CHAR_BUDGET,
) -> tuple[EvidenceItem, ...]:
    """Globally rank by score with a >=1 quota per non-empty source."""
    pools = {
        "knowledge": _aggregate_by_locator(_deduplicate(knowledge)),
        "session_file": _aggregate_by_locator(_deduplicate(session_files)),
        "web": _aggregate_by_locator(_deduplicate(web)),
    }
    ranked = {key: sorted(pool, key=_evidence_rank) for key, pool in pools.items()}
    selected: list[EvidenceItem] = []
    taken: set[str] = set()

    def take(item: EvidenceItem) -> None:
        taken.add(item.evidence_id)
        selected.append(item)

    # 每来源保底：只要来源非空且尚未入选，为其保留至少 1 条最高分证据
    for source_kind in _SOURCE_ORDER:
        if len(selected) == limit:
            break
        for item in ranked[source_kind]:
            take(item)
            break

    candidates = [item for pool in ranked.values() for item in pool]
    for item in sorted(candidates, key=_evidence_rank):
        if len(selected) == limit:
            break
        if item.evidence_id in taken:
            continue
        take(item)

    # 保底只保证名额；输出顺序仍按全局分数
    ordered = tuple(sorted(selected[:limit], key=_evidence_rank))
    return _enforce_total_budget(ordered, budget=char_budget)


def _deduplicate(items: tuple[EvidenceItem, ...]) -> tuple[EvidenceItem, ...]:
    result: list[EvidenceItem] = []
    seen_ids: set[str] = set()
    for item in items:
        if item.evidence_id in seen_ids:
            continue
        seen_ids.add(item.evidence_id)
        result.append(item)
    return tuple(result)


def _new_queries(values: tuple[str, ...], executed: set[str]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = value.casefold()
        if normalized in executed:
            continue
        executed.add(normalized)
        result.append(value)
    return tuple(result)


def _limit_quotes(
    evidence_items: tuple[EvidenceItem, ...], *, limit: int
) -> tuple[EvidenceItem, ...]:
    return tuple(
        replace(item, quote=item.quote[:limit])
        if len(item.quote) > limit
        else item
        for item in evidence_items
    )


def _finalize_draft_with_validation(
    draft: SynthesisDraft,
    evidence_items: tuple[EvidenceItem, ...],
    retrieval_limitations: tuple[str, ...],
    *,
    hint: str | None = None,
) -> TurnResult:
    """B9 flag-on 路径：先按原 finalize 语义裁剪，再用规则引擎逐 claim 校验。

    校验失败（无任何证据支持或被判冲突）的 claim 丢弃并把原因记入 limitations；
    全部 claim 失败时保持旧报错路径（model-response-invalid）作为最后兜底。
    """
    result = _finalize_draft(draft, evidence_items, retrieval_limitations)
    try:
        from app.citations.runtime_adapter import validate_claims
    except Exception:  # pragma: no cover - citations 包损坏时降级回旧行为
        return result

    try:
        reports = validate_claims(result.claims, evidence_items)
    except Exception:
        return result

    unsupported = [report for report in reports if not report.supported]
    if not unsupported:
        return result
    if len(unsupported) == len(reports):
        # 所有 claim 均未获支持：回退为不做校验的旧行为（保留引用编号答案）
        base = _finalize_draft(draft, evidence_items, retrieval_limitations)
        reasons = "; ".join(
            reason for report in unsupported[:2] for reason in report.reasons[:1]
        )
        return TurnResult(
            schema_version=base.schema_version,
            answer=base.answer,
            claims=base.claims,
            evidence=base.evidence,
            limitations=tuple(
                dict.fromkeys((*base.limitations, "部分陈述未获证据支持。", reasons))
            ),
        )

    known_ids = {item.evidence_id for item in evidence_items}
    # result.claims 的 claim_id 是 _finalize_draft 按索引生成的（claim-N），
    # 与 draft.claims 的对应关系用 statement 维持。
    keep_statements = {
        report.claim.statement for report in reports if report.supported
    }
    valid_claims = tuple(
        claim for claim in result.claims if claim.statement in keep_statements
    )
    drop_reasons = "; ".join(
        reason for report in unsupported for reason in report.reasons[:1]
    )
    cited_ids = tuple(
        dict.fromkeys(
            evidence_id for claim in valid_claims for evidence_id in claim.evidence_ids
        )
    )
    evidence_by_id = {item.evidence_id: item for item in evidence_items}
    cited_evidence = tuple(evidence_by_id[eid] for eid in cited_ids)
    evidence_numbers = {
        item.evidence_id: index for index, item in enumerate(cited_evidence, start=1)
    }
    paragraphs: list[str] = []
    for section in draft.sections:
        section_claims = [
            claim
            for index in section.claim_indexes
            for claim in [draft.claims[index] if index < len(draft.claims) else None]
            if claim is not None and claim.statement in keep_statements
        ]
        if section.claim_indexes and not section_claims:
            continue
        citations: list[int] = []
        for claim in section_claims:
            for evidence_id in claim.evidence_ids:
                if evidence_id in known_ids:
                    number = evidence_numbers[evidence_id]
                    if number not in citations:
                        citations.append(number)
        suffix = (
            "" if not citations else " " + "".join(f"[{n}]" for n in citations)
        )
        paragraphs.append(section.text.strip() + suffix)
    if not paragraphs:
        raise TurnExecutionError("model-response-invalid")
    return TurnResult(
        schema_version=result.schema_version,
        answer="\n\n".join(paragraphs),
        claims=valid_claims,
        evidence=cited_evidence,
        limitations=tuple(
            dict.fromkeys(
                (
                    *retrieval_limitations,
                    *draft.limitations,
                    "以下陈述未获证据支持，已从回答中移除。",
                    drop_reasons,
                )
            )
        ),
    )


def _finalize_draft(
    draft: SynthesisDraft,
    evidence_items: tuple[EvidenceItem, ...],
    retrieval_limitations: tuple[str, ...],
) -> TurnResult:
    known = {item.evidence_id for item in evidence_items}
    valid_claims: list[Claim] = []
    claim_index_map: dict[int, int] = {}
    for index, candidate in enumerate(draft.claims):
        evidence_ids = tuple(
            evidence_id
            for evidence_id in candidate.evidence_ids
            if evidence_id in known
        )
        if not evidence_ids:
            continue
        claim_index_map[index] = len(valid_claims)
        valid_claims.append(
            Claim(
                claim_id=f"claim-{len(valid_claims) + 1}",
                statement=candidate.statement,
                evidence_ids=evidence_ids,
            )
        )
    if evidence_items and not valid_claims:
        raise TurnExecutionError("model-response-invalid")

    cited_ids = tuple(
        dict.fromkeys(
            evidence_id
            for claim in valid_claims
            for evidence_id in claim.evidence_ids
        )
    )
    evidence_by_id = {item.evidence_id: item for item in evidence_items}
    cited_evidence = tuple(evidence_by_id[evidence_id] for evidence_id in cited_ids)
    evidence_numbers = {
        item.evidence_id: index for index, item in enumerate(cited_evidence, start=1)
    }
    paragraphs: list[str] = []
    for section in draft.sections:
        mapped = [
            claim_index_map[index]
            for index in section.claim_indexes
            if index in claim_index_map
        ]
        if section.claim_indexes and not mapped:
            continue
        citations: list[int] = []
        for index in mapped:
            for evidence_id in valid_claims[index].evidence_ids:
                number = evidence_numbers[evidence_id]
                if number not in citations:
                    citations.append(number)
        suffix = (
            ""
            if not citations
            else " " + "".join(f"[{number}]" for number in citations)
        )
        paragraphs.append(section.text.strip() + suffix)
    if not paragraphs:
        raise TurnExecutionError("model-response-invalid")
    limitations = tuple(dict.fromkeys((*retrieval_limitations, *draft.limitations)))
    return TurnResult(
        schema_version=SCHEMA_VERSION,
        answer="\n\n".join(paragraphs),
        claims=tuple(valid_claims),
        evidence=cited_evidence,
        limitations=limitations,
    )
