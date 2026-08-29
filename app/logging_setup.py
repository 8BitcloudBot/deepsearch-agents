"""轻量服务端日志装配（治理轮 G2）。

服务端日志不承担用户面文案（用户面走 model.py 的稳定枚举），只记录
装配降级、DAG 节点走向与模型 usage 等诊断信息。默认 INFO；
DEEPSEARCH_TRACE 开启后 DEBUG（DAG 节点进出日志只在 trace 级输出）。

脱敏约束：日志消息不得包含密钥与凭据；异常诊断一律先记异常类型，
消息体截断到 200 字符。
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping

_TRACE_VALUES = {"1", "true", "yes", "on"}


def trace_requested(environ: Mapping[str, str] | None = None) -> bool:
    env = environ if environ is not None else os.environ
    return str(env.get("DEEPSEARCH_TRACE", "")).strip().casefold() in _TRACE_VALUES


def configure_logging(environ: Mapping[str, str] | None = None) -> None:
    """幂等装配：默认 INFO，DEEPSEARCH_TRACE 时 DEBUG。"""
    level = logging.DEBUG if trace_requested(environ) else logging.INFO
    root = logging.getLogger("deepsearch")
    if root.handlers:
        root.setLevel(level)
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    )
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False


def brief(exc: BaseException) -> str:
    """异常诊断的安全摘要：类型名 + 截断消息，避免整段透传。"""
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def log_model_usage(logger: logging.Logger, role: str, response: object) -> None:
    """记录模型响应的 token usage；缺失（测试桩/旧 SDK）时静默跳过。"""
    metadata = getattr(response, "response_metadata", None)
    usage = metadata.get("token_usage") if isinstance(metadata, dict) else None
    if not isinstance(usage, dict):
        return
    logger.info(
        "model usage role=%s prompt=%s completion=%s total=%s",
        role,
        usage.get("prompt_tokens"),
        usage.get("completion_tokens"),
        usage.get("total_tokens"),
    )
