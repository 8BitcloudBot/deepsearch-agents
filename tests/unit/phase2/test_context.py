"""Tests for SessionContext and ContextVar lifecycle."""

import pytest

from app.api.context import SessionContext, current_session, session_context


class TestSessionContext:
    def test_session_context_stores_thread_id_and_workspace(self):
        from app.tools.files import SessionWorkspace

        ws = SessionWorkspace(
            thread_id="00000000-0000-4000-8000-000000000001",
            base_upload="/tmp/u",
            base_output="/tmp/o",
        )
        ctx = SessionContext(
            thread_id="00000000-0000-4000-8000-000000000001",
            workspace=ws,
        )
        assert ctx.thread_id.startswith("00000000")

    def test_current_session_raises_when_no_context(self):
        with pytest.raises(RuntimeError):
            current_session()

    def test_session_context_sets_and_resets(self):
        from app.tools.files import SessionWorkspace

        ws = SessionWorkspace(
            thread_id="thread-1",
            base_upload="/tmp/u",
            base_output="/tmp/o",
        )
        ctx = SessionContext(thread_id="thread-1", workspace=ws)
        with session_context(ctx):
            s = current_session()
            assert s.thread_id == "thread-1"
        with pytest.raises(RuntimeError):
            current_session()

    def test_nested_context_restores_outer(self):
        from app.tools.files import SessionWorkspace

        ws_inner = SessionWorkspace(
            thread_id="inner",
            base_upload="/tmp/inner_u",
            base_output="/tmp/inner_o",
        )
        SessionContext(thread_id="inner", workspace=ws_inner)

        with pytest.raises(RuntimeError):
            current_session()  # no outer context
