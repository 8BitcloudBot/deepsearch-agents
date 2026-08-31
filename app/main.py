"""Default FastAPI entry point for the agent-research product."""

import os
from pathlib import Path

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Create the user-facing agent-research application."""
    import logging

    from app.api.server import create_app as create_server
    from app.conversation.runtime import build_conversation_application

    root = Path.cwd()
    application = build_conversation_application(
        os.environ,
        runtime_root=root,
        store_path=Path(os.getenv("DEEPSEARCH_SQLITE", ".data/conversations.sqlite3")),
        report_root=Path(os.getenv("DEEPSEARCH_REPORT_ROOT", ".data/reports")),
    )
    # 3.6 认证边界：预置演示口令仅限本地使用，公网部署必须先改密
    demo_password = os.getenv("DEEPSEARCH_ALLOW_DEMO_PASSWORD", "").strip().casefold()
    if demo_password not in ("1", "true", "yes", "on"):
        logging.getLogger("deepsearch.runtime").warning(
            "认证为本地演示级（预置口令 user/admin / 0000，无登录限流）。"
            "仅限本机使用，请勿暴露公网；确认环境隔离后可设 "
            "DEEPSEARCH_ALLOW_DEMO_PASSWORD=true 关闭本提示。"
        )

    return create_server(
        store=application.store,
        conversation_application=application,
    )


# 模块级实例：uvicorn app.main:app 直跑入口（H1；装配本身 lazy 无外部连接）
app = create_app()
