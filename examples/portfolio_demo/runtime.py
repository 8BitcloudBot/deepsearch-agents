"""Fixture-backed executor for the deterministic portfolio demonstration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from app.agent.runtime import RuntimeRequest
from app.api.events import InMemoryEventBus
from app.knowledge.contracts import KnowledgeRetriever
from app.showcase.contracts import Limitation, SourceKind
from app.showcase.locator_adapters import (
    normalize_knowledge_chunk,
    normalize_mysql_row,
    normalize_tavily_hit,
    normalize_uploaded_span,
)
from app.showcase.research import LiveSourceCollector
from app.showcase.source_tools import ShowcaseProviders, create_showcase_source_tools

DemoScenario = Literal["success", "degraded", "failure", "formal-knowledge"]
DEMO_SCENARIOS: tuple[DemoScenario, ...] = (
    "success",
    "degraded",
    "failure",
    "formal-knowledge",
)
FIXTURE_ROOT = Path(__file__).with_name("fixtures")
UPLOAD_NAME = "showcase-notes.txt"


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def scenario_limitations(scenario: DemoScenario) -> tuple[Limitation, ...]:
    if scenario == "degraded":
        return (
            Limitation(
                code="knowledge-unavailable",
                source_kind=SourceKind.KNOWLEDGE,
                message="formal knowledge collection is unavailable in this demo",
            ),
        )
    return ()


class PortfolioDemoExecutor:
    """Collect repository fixtures through the production locator contracts."""

    def __init__(
        self,
        scenario: DemoScenario,
        *,
        events: InMemoryEventBus,
        knowledge_retriever: KnowledgeRetriever | None = None,
    ):
        self._scenario = scenario
        self._events = events
        self._knowledge_retriever = knowledge_retriever

    async def _collect_formal_knowledge(
        self, request: RuntimeRequest, collector: LiveSourceCollector
    ) -> str:
        if self._knowledge_retriever is None:
            raise RuntimeError("formal knowledge retriever is unavailable")
        tools = create_showcase_source_tools(
            ShowcaseProviders(knowledge=self._knowledge_retriever),
            self._events,
            captured_at=lambda: "2026-08-13T00:00:00Z",
            mysql_locator_context=None,
            uploads_enabled=False,
        )
        config: dict[str, Any] = {"configurable": {"thread_id": collector.thread_id}}
        return await tools.knowledge_tools[0].ainvoke(
            {"query": request.query, "limit": 8}, config=config
        )

    async def run(self, request: RuntimeRequest, collector: LiveSourceCollector) -> str:
        if self._scenario == "failure":
            raise RuntimeError(
                "token=raw-secret from /Users/portfolio/private/provider-response.json"
            )

        collector.add(
            normalize_tavily_hit(load_fixture("web.json")),
            quote="The Web fixture records the public DeepAgents research workflow.",
        )
        collector.add(
            normalize_mysql_row(load_fixture("mysql.json")),
            quote="The read-only MySQL fixture records a structured framework row.",
        )
        if self._scenario == "formal-knowledge":
            model_visible = await self._collect_formal_knowledge(request, collector)
            if model_visible == "Knowledge source unavailable.":
                raise RuntimeError("formal knowledge search returned no evidence")
        elif self._scenario == "success":
            knowledge = load_fixture("knowledge.json")
            collector.add(
                normalize_knowledge_chunk(
                    knowledge,
                    title=str(knowledge["title"]),
                ),
                quote="The local knowledge fixture records the retrieval boundary.",
            )

        upload_path = request.context.workspace.resolve_upload(UPLOAD_NAME)
        upload_text = upload_path.read_text(encoding="utf-8")
        uploaded = {
            "thread_id": collector.thread_id,
            "artifact_name": UPLOAD_NAME,
            "position": {
                "line_start": 1,
                "line_end": 1,
                "char_start": 0,
                "char_end": len(upload_text),
            },
            "title": "Portfolio demonstration notes",
            "display_text": upload_text,
            "captured_at": "2026-08-12T12:00:00Z",
            "version": "1.0.0",
        }
        collector.add(
            normalize_uploaded_span(uploaded, expected_thread_id=collector.thread_id),
            quote="The uploaded note defines the local comparison constraints.",
        )

        if self._scenario == "degraded":
            return (
                "The deterministic demonstration combines Web, read-only MySQL, "
                "and an uploaded constraint file.\n\n"
                "The formal knowledge collection is intentionally unavailable, "
                "so the result preserves that limitation instead of inventing evidence."
            )
        if self._scenario == "formal-knowledge":
            return (
                "The local formal-knowledge demonstration combines repository-safe "
                "Web and MySQL fixtures, a thread-scoped upload, and evidence "
                "retrieved "
                "from the path-backed Qdrant Local index.\n\n"
                "The knowledge evidence keeps its official title and shared "
                "collection, document, and chunk identity across the API, React, "
                "Markdown, and PDF contracts."
            )
        return (
            "The deterministic demonstration combines Web, read-only MySQL, local "
            "knowledge retrieval, and an uploaded constraint file.\n\n"
            "Every claim links to validated evidence and is delivered through the "
            "existing API, WebSocket, React, Markdown, and PDF contracts."
        )
