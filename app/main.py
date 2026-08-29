"""Default FastAPI entry point for the agent-research product."""

import os
from pathlib import Path

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Create the user-facing agent-research application."""
    from app.api.server import create_app as create_server
    from app.conversation.runtime import build_conversation_application

    root = Path.cwd()
    application = build_conversation_application(
        os.environ,
        runtime_root=root,
        store_path=Path(os.getenv("DEEPSEARCH_SQLITE", ".data/conversations.sqlite3")),
        report_root=Path(os.getenv("DEEPSEARCH_REPORT_ROOT", ".data/reports")),
    )
    return create_server(
        store=application.store,
        conversation_application=application,
    )


# 模块级实例：uvicorn app.main:app 直跑入口（H1；装配本身 lazy 无外部连接）
app = create_app()
