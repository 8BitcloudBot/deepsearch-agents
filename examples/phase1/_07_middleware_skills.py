"""Observable middleware and real skills loading.

Testable interfaces for RecordingMiddleware and SkillsMiddleware.
Phase 1-2: Skills loading uses real SkillsMiddleware.before_agent().
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from deepagents.backends.filesystem import FilesystemBackend
from deepagents.middleware.skills import SkillMetadata, SkillsMiddleware
from langchain.agents.middleware import AgentMiddleware
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime


@dataclass(frozen=True)
class MiddlewareEvent:
    """Structured, safe-to-log middleware event. No secrets."""

    request_id: str
    phase: str
    model_name: str
    input_message_count: int
    output_message_count: int | None = None
    duration_ms: float | None = None
    error_type: str | None = None


class RecordingMiddleware(AgentMiddleware):
    """Middleware that records structured events via wrap_model_call."""

    def __init__(
        self,
        events: list[MiddlewareEvent],
        clock: Callable[[], float],
        request_id_factory: Callable[[], str],
    ):
        super().__init__()
        self._events = events
        self._clock = clock
        self._request_id_factory = request_id_factory

    def wrap_model_call(self, request, handler):
        rid = self._request_id_factory()
        model_name = _safe_model_name(request)
        input_count = len(request.messages)

        self._events.append(
            MiddlewareEvent(
                request_id=rid,
                phase="started",
                model_name=model_name,
                input_message_count=input_count,
            )
        )

        start = self._clock()
        try:
            response = handler(request)
            duration_ms = (self._clock() - start) * 1000
            output_count = len(response.result)
            self._events.append(
                MiddlewareEvent(
                    request_id=rid,
                    phase="completed",
                    model_name=model_name,
                    input_message_count=input_count,
                    output_message_count=output_count,
                    duration_ms=duration_ms,
                )
            )
            return response
        except Exception as exc:
            duration_ms = (self._clock() - start) * 1000
            self._events.append(
                MiddlewareEvent(
                    request_id=rid,
                    phase="failed",
                    model_name=model_name,
                    input_message_count=input_count,
                    duration_ms=duration_ms,
                    error_type=type(exc).__name__,
                )
            )
            raise


def _safe_model_name(request) -> str:
    model = getattr(request, "model", None)
    if model is None:
        return "unknown"
    name = getattr(model, "model_name", None)
    if name:
        return str(name)
    return type(model).__name__


def build_recording_middleware(
    *,
    events: list[MiddlewareEvent],
    clock: Callable[[], float],
    request_id_factory: Callable[[], str],
) -> RecordingMiddleware:
    return RecordingMiddleware(
        events=events,
        clock=clock,
        request_id_factory=request_id_factory,
    )


# ---- SkillsMiddleware real loading (Phase 1-2) ----


def create_skills_middleware(root: Path) -> SkillsMiddleware:
    """Create SkillsMiddleware loading skills from root directory.

    Uses a real FilesystemBackend (no virtual_mode) so that
    SkillsMiddleware can read the source directory via the backend.
    """
    be = FilesystemBackend(root_dir=str(root), virtual_mode=False)
    return SkillsMiddleware(backend=be, sources=[str(root)])


def load_skills_metadata(
    middleware: SkillsMiddleware,
    *,
    runtime: Runtime,
    config: RunnableConfig | None = None,
) -> list[SkillMetadata]:
    """Load parsed skill metadata through the public middleware lifecycle.

    Calls middleware.before_agent() with an empty state. Returns the
    list of SkillMetadata discovered, or empty list if skills_metadata
    key already existed in state (returns None).
    """
    update = middleware.before_agent({}, runtime, config or {})
    if update is None:
        return []
    return list(update.get("skills_metadata", []))
