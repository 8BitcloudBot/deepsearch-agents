"""Pydantic output contracts bridging raw model JSON into adapter payloads (B2).

模型返回的 JSON 可能带类型毛刺或形状漂移；这里用 Pydantic 把三角色输出
规范化为适配器消费的 canonical dict。校验失败时返回原 payload——调用方
继续走既有的宽容解析路径，失败语义（ValueError "model response is invalid"）
与旧实现完全一致，属保守双保险而非收紧。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError


class PlanOutput(BaseModel):
    objective: str
    subquestions: list[str] = []
    knowledge_queries: list[str] = []
    web_queries: list[str] = []
    research_intensity: str | None = None
    search_hints: dict[str, str] | None = None


class ReviewOutput(BaseModel):
    uncovered_questions: list[str] = []
    knowledge_queries: list[str] = []
    web_queries: list[str] = []


class SynthesisSectionModel(BaseModel):
    text: str
    claim_indexes: list[int] = []


class SynthesisClaimModel(BaseModel):
    statement: str
    evidence_ids: list[str] = []


class SynthesisOutput(BaseModel):
    answer_sections: list[SynthesisSectionModel]
    claims: list[SynthesisClaimModel]
    limitations: list[Any] = []


def _coerce(model_cls: type[BaseModel], payload: Any) -> Any:
    try:
        return model_cls.model_validate(payload).model_dump()
    except ValidationError:
        # 形状无法识别时原样交还，由既有解析路径给出稳定的失败语义
        return payload


def coerce_plan_output(payload: dict[str, Any]) -> dict[str, Any]:
    return _coerce(PlanOutput, payload)


def coerce_review_output(payload: dict[str, Any]) -> dict[str, Any]:
    return _coerce(ReviewOutput, payload)


def coerce_synthesis_output(payload: dict[str, Any]) -> dict[str, Any]:
    return _coerce(SynthesisOutput, payload)
