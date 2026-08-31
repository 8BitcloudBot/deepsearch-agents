"""B2 结构化输出：噪声剥离、Pydantic 双保险、通道 flag、错误分类。"""

import pytest

from app.conversation.model import classify_model_error
from app.conversation.output_schemas import (
    coerce_plan_output,
    coerce_review_output,
    coerce_synthesis_output,
)
from app.conversation.runtime import _strict_json
from app.conversation.settings import ConversationSettings


def _response(content: str) -> object:
    return type("Response", (), {"content": content})()


def test_strict_json_extracts_payload_with_surrounding_noise() -> None:
    raw = (
        "好的，以下是计划。\n"
        '```json\n{"objective":"x"}\n```\n'
        "补充说明完毕。"
    )

    assert _strict_json(_response(raw)) == {"objective": "x"}


def test_strict_json_window_recovers_prefixed_noise_without_fence() -> None:
    raw = '开始说明 {"objective": "目标", "note": {}} 结束。'

    assert _strict_json(_response(raw))["objective"] == "目标"


def test_strict_json_rejects_json_less_noise() -> None:
    with pytest.raises(ValueError):
        _strict_json(_response("完全没有任何 JSON 的输出"))


def test_plan_coercion_fixes_type_drift_and_passes_through_junk() -> None:
    good = coerce_plan_output(
        {"objective": "目标", "subquestions": ("a",), "extra_field": True}
    )
    # v2 list[str] 接受 iterable → 元组收敛为规范列表；额外字段被忽略
    assert good["objective"] == "目标"
    assert good["subquestions"] == ["a"]
    assert "extra_field" not in good

    # int 不是 str 的合法 lax 来源 → 校验失败原样透传，交由既有解析路径给出旧语义
    junk = {"objective": 1}
    assert coerce_plan_output(junk) is junk


def test_review_and_synthesis_coercion_shapes() -> None:
    review = coerce_review_output({"uncovered_questions": "缺口"})
    # 字符串不能收敛为 list[str] → 原样返回
    assert review == {"uncovered_questions": "缺口"}

    shaped = coerce_synthesis_output(
        {
            "answer_sections": [{"text": "段", "claim_indexes": [0, 1]}],
            "claims": [{"statement": "陈", "evidence_ids": ["ev-1"]}],
            "limitations": [{"type": "t", "detail": "d"}],
        }
    )
    assert shaped["answer_sections"][0]["claim_indexes"] == [0, 1]
    assert shaped["limitations"][0]["detail"] == "d"


def test_structured_output_flag_binds_json_object_mode(monkeypatch) -> None:
    bound_calls: list[dict] = []

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            pass

        def bind(self, **kwargs):
            bound_calls.append(kwargs)
            return object()

    monkeypatch.setattr("langchain_openai.ChatOpenAI", FakeChatOpenAI)
    from app.conversation.model import build_agent_model

    settings_on = ConversationSettings.from_env(
        {
            "MODEL_NAME": "m",
            "MODEL_API_KEY": "k",  # pragma: allowlist secret — 测试假值
            "MODEL_STRUCTURED_OUTPUT": "true",
        }
    )
    build_agent_model(settings_on)
    assert bound_calls == [{"response_format": {"type": "json_object"}}]

    settings_off = ConversationSettings.from_env(
        {"MODEL_NAME": "m", "MODEL_API_KEY": "k"}  # pragma: allowlist secret — 测试假值
    )
    _, descriptor_off = build_agent_model(settings_off)
    assert len(bound_calls) == 1  # 关闭态不发生绑定


def test_classify_model_error_uses_exception_types_first() -> None:
    openai_err = pytest.importorskip("openai")
    import httpx

    def http_response(status_code: int) -> httpx.Response:
        return httpx.Response(
            status_code,
            request=httpx.Request("POST", "https://api.example.com/v1/chat"),
        )

    class StatusLike(openai_err.APIStatusError):
        def __init__(self, status_code: int):
            super().__init__(
                message="irrelevant text without codes",
                response=http_response(status_code),
                body=None,
            )

    assert classify_model_error(StatusLike(429)).code == "model-rate-limit"
    assert classify_model_error(StatusLike(403)).code == "model-authentication"
    assert classify_model_error(StatusLike(503)).code == "model-unavailable"
    assert classify_model_error(StatusLike(400)).code == "model-failed"

    # 文本兜底仍在：非 openai 异常走旧映射
    class PlainError(Exception):
        pass

    assert (
        classify_model_error(PlainError("HTTP 401 Unauthorized from somewhere")).code
        == "model-authentication"
    )
