"""OpenAI-compatible model construction and safe failure categories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.conversation.settings import ConversationSettings

ModelErrorCode = Literal[
    "model-authentication",
    "model-timeout",
    "model-rate-limit",
    "model-unavailable",
    "model-response-invalid",
    "model-failed",
]

_MODEL_MESSAGES: dict[ModelErrorCode, str] = {
    "model-authentication": "研究模型配置不可用，请检查服务端配置后重试",
    "model-timeout": "研究模型请求超时，请稍后重试",
    "model-rate-limit": "研究模型请求过于频繁，请稍后重试",
    "model-unavailable": "研究模型暂时不可用，请稍后重试",
    "model-response-invalid": "研究模型返回内容无效，请稍后重试",
    "model-failed": "研究模型调用失败，请稍后重试",
}


@dataclass(frozen=True)
class ModelDescriptor:
    provider: Literal["openai-compatible"]
    model: str
    base_url_configured: bool


class ModelUnavailable(RuntimeError):  # noqa: N818 - public contract name
    def __init__(self, code: ModelErrorCode, *, configuration: bool = False):
        self.code = code
        self.retryable = code in {"model-rate-limit", "model-unavailable"}
        message = "研究模型配置不可用" if configuration else "研究模型调用失败"
        super().__init__(message)

    @property
    def safe_message(self) -> str:
        return _MODEL_MESSAGES.get(self.code, "研究模型调用失败，请稍后重试")


def build_agent_model(
    settings: ConversationSettings,
) -> tuple[Any, ModelDescriptor]:
    if not settings.model_api_key or not settings.model_name:
        raise ModelUnavailable("model-authentication", configuration=True)

    from langchain_openai import ChatOpenAI

    kwargs: dict[str, object] = {
        "model": settings.model_name,
        "api_key": settings.model_api_key,
        "timeout": settings.model_timeout_seconds,
        "max_retries": settings.model_max_retries,
    }
    if settings.model_temperature is not None:
        kwargs["temperature"] = settings.model_temperature
    if settings.model_top_p is not None:
        kwargs["top_p"] = settings.model_top_p
    if settings.model_base_url is not None:
        kwargs["base_url"] = settings.model_base_url
    model = ChatOpenAI(**kwargs)
    return model, ModelDescriptor(
        provider="openai-compatible",
        model=settings.model_name,
        base_url_configured=settings.model_base_url is not None,
    )


def classify_model_error(exc: Exception) -> ModelUnavailable:
    text = str(exc).lower()
    if isinstance(exc, TimeoutError) or "timeout" in text or "timed out" in text:
        code: ModelErrorCode = "model-timeout"
    elif isinstance(exc, PermissionError) or "401" in text or "unauthorized" in text:
        code = "model-authentication"
    elif "429" in text or "rate limit" in text or "rate_limit" in text:
        code = "model-rate-limit"
    elif "unavailable" in text or "connection" in text:
        code = "model-unavailable"
    elif "response" in text or "json" in text:
        code = "model-response-invalid"
    else:
        code = "model-failed"
    return ModelUnavailable(code)
