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
        upload_root=Path(os.getenv("DEEPSEARCH_UPLOAD_ROOT", ".data/uploads")),
    )
