"""G2 日志层：trace 开关、usage 计量、异常摘要、装配降级可见性。"""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.conversation.runtime import build_conversation_application
from app.logging_setup import (
    brief,
    configure_logging,
    log_model_usage,
    trace_requested,
)


def test_trace_requested_defaults_off_and_parses_truthy() -> None:
    assert trace_requested({}) is False
    assert trace_requested({"DEEPSEARCH_TRACE": ""}) is False
    assert trace_requested({"DEEPSEARCH_TRACE": "0"}) is False
    for value in ("1", "true", "YES", "on"):
        assert trace_requested({"DEEPSEARCH_TRACE": value}) is True


def test_configure_logging_is_idempotent_and_honors_trace() -> None:
    root = logging.getLogger("deepsearch")
    saved_handlers = list(root.handlers)
    saved_level = root.level
    saved_propagate = root.propagate
    try:
        for handler in list(root.handlers):
            root.removeHandler(handler)
        configure_logging({})
        assert root.level == logging.INFO
        assert len(root.handlers) == 1
        configure_logging({"DEEPSEARCH_TRACE": "1"})
        assert root.level == logging.DEBUG
        assert len(root.handlers) == 1  # 幂等：不重复挂 handler
    finally:
        for handler in list(root.handlers):
            root.removeHandler(handler)
        for handler in saved_handlers:
            root.addHandler(handler)
        root.setLevel(saved_level)
        root.propagate = saved_propagate


def test_log_model_usage_extracts_token_counts(
    caplog: pytest.LogCaptureFixture,
) -> None:
    response = SimpleNamespace(
        response_metadata={
            "token_usage": {
                "prompt_tokens": 120,
                "completion_tokens": 80,
                "total_tokens": 200,
            }
        }
    )
    logger = logging.getLogger("test.usage")
    with caplog.at_level(logging.INFO, logger="test.usage"):
        log_model_usage(logger, "planner", response)
    assert "role=planner" in caplog.text
    assert "prompt=120" in caplog.text
    assert "total=200" in caplog.text


def test_log_model_usage_silently_skips_missing_metadata() -> None:
    class Bare:
        pass

    log_model_usage(logging.getLogger("test.usage"), "planner", Bare())
    log_model_usage(logging.getLogger("test.usage"), "planner", None)


def test_brief_truncates_and_keeps_exception_type() -> None:
    assert brief(ValueError("boom")).startswith("ValueError: boom")
    assert brief(ValueError("x" * 500)) == f"ValueError: {'x' * 200}"


def test_build_survives_embedder_failure_and_keeps_degradation_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def _boom(**_kwargs: object) -> None:
        raise RuntimeError("embedder constructor exploded")

    import app.knowledge.embeddings as embeddings_module

    monkeypatch.setattr(embeddings_module, "FastEmbedEmbeddingAdapter", _boom)
    # configure_logging 关闭命名空间传播且先于记录发生；直接在发日志的
    # logger 上挂捕获 handler 验证降级可见性
    records: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record.getMessage())

    runtime_logger = logging.getLogger("deepsearch.runtime")
    capture = _Capture(level=logging.WARNING)
    runtime_logger.addHandler(capture)
    try:
        application = build_conversation_application(
            {},
            runtime_root=tmp_path,
            store_path=tmp_path / "state.sqlite3",
            report_root=tmp_path / "reports",
        )
    finally:
        runtime_logger.removeHandler(capture)
    assert application.upload_store is None
    assert application.capabilities["knowledge"]["status"] == "unavailable"
    assert any("embedding adapter unavailable" in message for message in records)
