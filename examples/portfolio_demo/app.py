"""FastAPI factory for the deterministic Phase 9 portfolio demonstration."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.events import InMemoryEventBus
from app.api.server import create_app as create_server
from app.knowledge.contracts import KnowledgeRetriever
from app.settings import Phase2Settings
from app.showcase.delivery import ShowcaseCitationDelivery
from app.showcase.runtime import ShowcaseResearchRuntime
from examples.portfolio_demo.runtime import (
    DEMO_SCENARIOS,
    DemoScenario,
    PortfolioDemoExecutor,
    scenario_limitations,
)


def create_demo_app(
    scenario: DemoScenario = "success",
    *,
    knowledge_retriever: KnowledgeRetriever | None = None,
) -> FastAPI:
    if scenario not in DEMO_SCENARIOS:
        raise ValueError(f"scenario must be one of {list(DEMO_SCENARIOS)}")
    if scenario == "formal-knowledge" and knowledge_retriever is None:
        raise ValueError("formal-knowledge scenario requires a knowledge retriever")

    events = InMemoryEventBus()
    runtime = ShowcaseResearchRuntime(
        events,
        PortfolioDemoExecutor(
            scenario,
            events=events,
            knowledge_retriever=knowledge_retriever,
        ),
        scenario_limitations(scenario),
        delivery=ShowcaseCitationDelivery(events),
    )
    app = create_server(
        settings=Phase2Settings(app_profile="showcase"),
        runtime=runtime,
        events=events,
    )
    app.state.portfolio_demo_scenario = scenario
    app.state.portfolio_demo_events = events
    return app


app = create_demo_app()

__all__ = ["app", "create_demo_app"]
