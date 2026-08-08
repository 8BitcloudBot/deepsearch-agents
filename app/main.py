"""Phase 2 FastAPI application entry point."""

from fastapi import FastAPI

from app.providers.factory import build_providers
from app.settings import Phase2Settings


def create_app() -> FastAPI:
    """Create and configure the Phase 2 FastAPI application.

    Returns a fully wired app with HTTP routes, WebSocket, and
    /health reporting phase: "2" without secrets.
    """
    from app.agent.factory import create_tutorial_agent
    from app.agent.runtime import MockTutorialRuntime
    from app.api.events import InMemoryEventBus
    from app.api.server import create_app as create_server

    settings = Phase2Settings.from_env()
    events = InMemoryEventBus()

    if settings.app_profile == "agent-research":
        # Offline deterministic research runtime — versioned corpus only,
        # no model, no Provider network. build_providers is never called,
        # so residual Phase 2 real-provider env vars without credentials
        # must not fail app startup.
        from app.research.runtime import AgentResearchRuntime

        runtime = AgentResearchRuntime(events)
        bundle = None
    elif settings.app_profile == "showcase":
        # P4.5-1: showcase is contract-only and inert. There is no live
        # source adapter or runtime yet (P4.5-2/P4.5-3); the profile runs
        # the same deterministic offline research runtime and must never
        # construct providers or read credentials. The dedicated opt-in
        # and capability surface live in app.showcase.contracts.
        from app.research.runtime import AgentResearchRuntime

        runtime = AgentResearchRuntime(events)
        bundle = None
    else:
        bundle = build_providers(settings)
        if settings.tutorial_runtime == "deepagents":
            # Real runtime requires a model
            from langchain_openai import ChatOpenAI

            if not settings.model_api_key:
                raise RuntimeError("MODEL_API_KEY required for deepagents runtime")
            model = ChatOpenAI(
                model=settings.model_name,
                api_key=settings.model_api_key,
                base_url=settings.model_base_url,
            )
            graph = create_tutorial_agent(model, bundle, events, lambda tid: None)
            from app.agent.runtime import DeepAgentsTutorialRuntime

            runtime = DeepAgentsTutorialRuntime(graph, bundle, events)
        else:
            runtime = MockTutorialRuntime(bundle, events)

    return create_server(
        settings=settings, bundle=bundle, runtime=runtime, events=events
    )
