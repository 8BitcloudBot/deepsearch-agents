"""Single SessionContext and ContextVar lifecycle.

Every HTTP request or background task that reads/writes thread-scoped
files must enter `session_context(ctx)`.  Tools and runtimes obtain the
current context through `current_session()`, never from a second global.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.tools.files import SessionWorkspace

_CURRENT: ContextVar["SessionContext | None"] = ContextVar(
    "phase2_current_session", default=None
)


@dataclass(frozen=True)
class SessionContext:
    thread_id: str
    workspace: "SessionWorkspace"


@contextmanager
def session_context(ctx: SessionContext):
    token = _CURRENT.set(ctx)
    try:
        yield
    finally:
        _CURRENT.reset(token)


def current_session() -> SessionContext:
    ctx = _CURRENT.get()
    if ctx is None:
        raise RuntimeError("No active SessionContext. Enter session_context() first.")
    return ctx
