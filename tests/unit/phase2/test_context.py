"""RED: Complete ContextVar lifecycle and nesting contract.

Covers nested restoration, exception-safe reset, and error message
redaction (no paths/credentials in errors).
"""

import pytest

from app.api.context import SessionContext, current_session, session_context
from app.tools.files import SessionWorkspace

UUID_V4 = "00000000-0000-4000-8000-000000000001"


def _workspace(thread_id: str = UUID_V4) -> SessionWorkspace:
    return SessionWorkspace.for_thread(
        thread_id=thread_id,
        base_upload=f"/tmp/up-{thread_id[:8]}",
        base_output=f"/tmp/out-{thread_id[:8]}",
    )


def _ctx(thread_id: str = UUID_V4) -> SessionContext:
    return SessionContext(thread_id=thread_id, workspace=_workspace(thread_id))


# ── Basic lifecycle ─────────────────────────────────────────────────────────


def test_current_session_raises_when_no_context():
    with pytest.raises(RuntimeError):
        current_session()


def test_session_context_sets_and_resets():
    ctx = _ctx("aaaaaaaa-0000-4000-8000-000000000001")
    with session_context(ctx):
        s = current_session()
        assert s.thread_id == "aaaaaaaa-0000-4000-8000-000000000001"
    with pytest.raises(RuntimeError):
        current_session()


def test_context_stores_thread_id_and_workspace():
    ws = _workspace()
    ctx = SessionContext(thread_id=UUID_V4, workspace=ws)
    assert ctx.thread_id == UUID_V4
    assert ctx.workspace is ws


# ── Nested restoration ─────────────────────────────────────────────────────


def test_nested_context_restores_outer():
    outer = _ctx("aaaaaaaa-0000-4000-8000-000000000001")
    inner = _ctx("bbbbbbbb-0000-4000-8000-000000000002")

    assert (
        current_session.__wrapped__ if hasattr(current_session, "__wrapped__") else True
    )
    with session_context(outer):
        assert current_session().thread_id == outer.thread_id
        with session_context(inner):
            assert current_session().thread_id == inner.thread_id
        # Back to outer
        assert current_session().thread_id == outer.thread_id
    # Outer gone
    with pytest.raises(RuntimeError):
        current_session()


def test_nested_context_exception_resets_both():
    outer = _ctx("aaaaaaaa-0000-4000-8000-000000000001")
    inner = _ctx("bbbbbbbb-0000-4000-8000-000000000002")

    try:
        with session_context(outer):
            with session_context(inner):
                raise ValueError("inner error")
    except ValueError:
        pass

    # Both must be reset
    with pytest.raises(RuntimeError):
        current_session()


def test_exception_inside_single_context_resets():
    ctx = _ctx()
    try:
        with session_context(ctx):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    with pytest.raises(RuntimeError):
        current_session()


# ── Error message redaction ─────────────────────────────────────────────────


def test_current_session_error_has_no_paths():
    with pytest.raises(RuntimeError) as exc_info:
        current_session()
    msg = str(exc_info.value)
    assert "/" not in msg, f"Error message contains path: {msg!r}"
    assert "\\" not in msg, f"Error message contains backslash: {msg!r}"


def test_current_session_error_has_no_credentials():
    with pytest.raises(RuntimeError) as exc_info:
        current_session()
    msg = str(exc_info.value).lower()
    for word in ("password", "secret", "token", "key", "credential"):
        assert word not in msg, f"Error message contains {word!r}: {msg!r}"
