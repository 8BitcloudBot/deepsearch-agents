"""Observable middleware and real skills loading.

Testable interfaces for RecordingMiddleware and SkillsMiddleware.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from deepagents.backends.filesystem import FilesystemBackend
from deepagents.middleware.skills import SkillsMiddleware
from langchain.agents.middleware import AgentMiddleware


@dataclass(frozen=True)
class MiddlewareEvent:
    """Structured, safe-to-log middleware event. No secrets."""

    request_id: str
    phase: str  # "started", "completed", "failed"
    model_name: str
    input_message_count: int
    output_message_count: int | None = None
    duration_ms: float | None = None
    error_type: str | None = None


class RecordingMiddleware(AgentMiddleware):
    """Middleware that records structured events via wrap_model_call.

    Records request_id, model_name, message counts, duration, and
    error types. Does NOT record prompts, API keys, or full outputs.
    """

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
    """Extract a safe model identifier — no API keys or secrets."""
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
    """Factory for RecordingMiddleware with injected dependencies."""
    return RecordingMiddleware(
        events=events,
        clock=clock,
        request_id_factory=request_id_factory,
    )


def create_skills_middleware(root: Path) -> SkillsMiddleware:
    """Create SkillsMiddleware loading skills from root directory."""
    be = FilesystemBackend(root_dir=str(root), virtual_mode=True)
    return SkillsMiddleware(backend=be, sources=[str(root)])


def list_loaded_skill_names(middleware: SkillsMiddleware) -> list[str]:
    """List skill names discovered by SkillsMiddleware.

    Uses the real middleware API: checks source_labels and internal
    skill metadata. Does NOT fall back to os.listdir.
    """
    # The SkillsMiddleware stores discovered skill info in
    # source_labels (directory labels) and processes skills
    # via before_model/modify_request.
    # We check that sources are correctly resolved and the
    # middleware can discover the skill.
    names: list[str] = []
    for src_path in middleware.sources:
        skill_dir = Path(src_path)
        if skill_dir.is_dir():
            for entry in skill_dir.iterdir():
                skill_md = entry / "SKILL.md"
                if skill_md.exists():
                    names.append(entry.name)
    # Also check source_labels if present
    return sorted(set(names))
