"""Thread-scoped live evidence collection for the P4.5-3 showcase runtime."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from app.agent.runtime import RuntimeResult
from app.citations.rules import redact
from app.showcase.contracts import Limitation, SourceKind
from app.showcase.locators import LocatorError, LocatorState, SourceLocator

MAX_LIVE_QUOTE_LENGTH = 2048

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)
_WS_RE = re.compile(r"\s+")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _safe_quote(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LocatorError("quote must be a non-empty string")
    normalized = _WS_RE.sub(" ", value).strip()
    return redact(normalized)[:MAX_LIVE_QUOTE_LENGTH]


@dataclass(frozen=True)
class LiveEvidence:
    """One validated live-source quote, kept outside frozen Phase 4 fixtures."""

    evidence_id: str
    source_id: str
    source_kind: SourceKind
    locator: dict[str, str]
    quote: str
    content_sha256: str
    thread_id: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "source_id": self.source_id,
            "source_kind": self.source_kind.value,
            "locator": dict(self.locator),
            "quote": self.quote,
            "content_sha256": self.content_sha256,
            "thread_id": self.thread_id,
        }


@dataclass(frozen=True)
class ShowcaseRunResult(RuntimeResult):
    """Internal runtime result; delivery is intentionally deferred to P4.5-4."""

    sources: tuple[SourceLocator, ...] = ()
    evidence: tuple[LiveEvidence, ...] = ()
    limitations: tuple[Limitation, ...] = ()


class LiveSourceCollector:
    """Validate and deduplicate live sources for exactly one thread."""

    def __init__(self, thread_id: str):
        if not isinstance(thread_id, str) or not _UUID_RE.fullmatch(thread_id):
            raise LocatorError("collector thread_id must be a UUID")
        self._thread_id = thread_id.lower()
        self._sources: dict[str, SourceLocator] = {}
        self._evidence: dict[str, LiveEvidence] = {}
        self._limitations: list[Limitation] = []

    @property
    def thread_id(self) -> str:
        return self._thread_id

    def add(self, source: SourceLocator, *, quote: str) -> LiveEvidence:
        if not isinstance(source, SourceLocator):
            raise LocatorError("source must be a SourceLocator")
        if source.state is not LocatorState.VALID:
            raise LocatorError(f"cannot collect {source.state.value} source locator")
        if source.thread_id is not None and source.thread_id != self._thread_id:
            raise LocatorError("source locator belongs to a different thread")
        expected_thread_id = (
            self._thread_id if source.source_kind is SourceKind.UPLOADED_FILE else None
        )
        source.as_live_source_result(expected_thread_id=expected_thread_id)

        safe_quote = _safe_quote(quote)
        locator = source.as_contract()
        content_sha256 = hashlib.sha256(safe_quote.encode("utf-8")).hexdigest()
        identity = _canonical_json(
            {
                "source_id": source.source_id,
                "locator": locator,
                "quote": safe_quote,
            }
        )
        evidence_id = (
            "ev-live-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
        )
        evidence = LiveEvidence(
            evidence_id=evidence_id,
            source_id=source.source_id,
            source_kind=source.source_kind,
            locator=locator,
            quote=safe_quote,
            content_sha256=content_sha256,
            thread_id=source.thread_id,
        )
        self._sources.setdefault(source.source_id, source)
        return self._evidence.setdefault(evidence_id, evidence)

    def add_limitation(self, limitation: Limitation) -> None:
        if not isinstance(limitation, Limitation):
            raise TypeError("limitation must be a Limitation")
        self._limitations.append(
            Limitation(
                code=limitation.code,
                source_kind=limitation.source_kind,
                message=redact(limitation.message),
            )
        )

    def snapshot(
        self, answer: str, artifacts: tuple[str, ...] = ()
    ) -> ShowcaseRunResult:
        safe_answer = redact(answer) if isinstance(answer, str) else ""
        return ShowcaseRunResult(
            answer=safe_answer,
            artifacts=tuple(artifacts),
            sources=tuple(self._sources.values()),
            evidence=tuple(self._evidence.values()),
            limitations=tuple(self._limitations),
        )


_CURRENT_COLLECTOR: ContextVar[LiveSourceCollector | None] = ContextVar(
    "showcase_live_source_collector", default=None
)


@contextmanager
def collector_context(collector: LiveSourceCollector) -> Iterator[None]:
    """Bind one request-local collector for reusable graph tool closures."""
    token = _CURRENT_COLLECTOR.set(collector)
    try:
        yield
    finally:
        _CURRENT_COLLECTOR.reset(token)


def current_collector() -> LiveSourceCollector:
    collector = _CURRENT_COLLECTOR.get()
    if collector is None:
        raise RuntimeError("No active LiveSourceCollector")
    return collector
