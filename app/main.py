"""Phase 2 FastAPI application entry point."""

import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI

from app.providers.factory import build_providers
from app.settings import Phase2Settings


def _showcase_captured_at() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_showcase_runtime(*, environ: Mapping[str, str], events):
    """Build the explicitly opted-in showcase runtime and its live adapters."""
    from app.showcase.agent import DeepAgentsShowcaseExecutor, create_showcase_agent
    from app.showcase.config import ShowcaseRuntimeConfig
    from app.showcase.contracts import Limitation, SourceKind
    from app.showcase.delivery import ShowcaseCitationDelivery
    from app.showcase.runtime import ShowcaseResearchRuntime
    from app.showcase.source_tools import (
        MySQLLocatorContext,
        ShowcaseProviders,
        create_showcase_source_tools,
    )

    config = ShowcaseRuntimeConfig.from_env(environ)
    delivery = ShowcaseCitationDelivery(events)
    if not config.model_available:
        return ShowcaseResearchRuntime(
            events, None, config.limitations, delivery=delivery
        )

    from langchain_openai import ChatOpenAI

    try:
        model = ChatOpenAI(
            model=config.model_name,
            api_key=config.model_api_key,
            base_url=config.model_base_url,
        )
    except Exception:
        limitation = Limitation(
            code="model-unavailable",
            source_kind=None,
            message="showcase model could not be initialized",
        )
        return ShowcaseResearchRuntime(
            events,
            None,
            config.limitations + (limitation,),
            delivery=delivery,
        )

    def source_ready(kind: SourceKind) -> bool:
        state = config.capabilities.check(kind)
        return state.enabled and not any(
            limitation.source_kind is kind for limitation in config.limitations
        )

    limitations = list(config.limitations)
    web = None
    catalog = None
    knowledge = None
    mysql_context = None

    if source_ready(SourceKind.WEB):
        from app.providers.tavily import TavilyWebProvider

        web = TavilyWebProvider(api_key=config.tavily_api_key or "")
    if source_ready(SourceKind.MYSQL):
        from app.providers.mysql import MySQLCatalogProvider

        catalog = MySQLCatalogProvider(
            host=config.mysql_host or "",
            port=config.mysql_port or 3307,
            user=config.mysql_user or "",
            password=config.mysql_password or "",
            database=config.mysql_database or "",
        )
        mysql_context = MySQLLocatorContext(
            connection_alias="showcase",
            database=config.mysql_database or "",
        )
    if source_ready(SourceKind.KNOWLEDGE):
        try:
            from app.knowledge.contracts import (
                KnowledgeIndexSpec,
                resolve_knowledge_index_path,
            )
            from app.knowledge.embeddings import FastEmbedEmbeddingAdapter
            from app.knowledge.qdrant_local import QdrantLocalKnowledgeIndex

            embedder = FastEmbedEmbeddingAdapter(
                model=config.knowledge_embedding_model or "",
                version=config.knowledge_embedding_version or "",
                dimension=config.knowledge_embedding_dimension or 384,
                cache_dir=str((Path.cwd() / ".cache" / "fastembed").resolve()),
            )
            spec = KnowledgeIndexSpec(
                collection_id=config.knowledge_collection or "",
                embedding=embedder.descriptor,
                distance="cosine",
                chunking_version=config.knowledge_chunking_version or "",
            )
            index_path = resolve_knowledge_index_path(
                config.knowledge_index_path or "",
                runtime_root=Path.cwd(),
            )
            knowledge = QdrantLocalKnowledgeIndex(
                index_path,
                spec,
                embedder,
                min_score=config.knowledge_min_score,
            )
        except Exception:
            limitations.append(
                Limitation(
                    code="knowledge-unavailable",
                    source_kind=SourceKind.KNOWLEDGE,
                    message="knowledge collection is unavailable",
                )
            )

    providers = ShowcaseProviders(web=web, catalog=catalog, knowledge=knowledge)
    tools = create_showcase_source_tools(
        providers,
        events,
        captured_at=_showcase_captured_at,
        mysql_locator_context=mysql_context,
        uploads_enabled=source_ready(SourceKind.UPLOADED_FILE),
    )
    graph = create_showcase_agent(model, tools)
    executor = DeepAgentsShowcaseExecutor(graph)
    return ShowcaseResearchRuntime(
        events, executor, tuple(limitations), delivery=delivery
    )


def create_app() -> FastAPI:
    """Create and configure the Phase 2 FastAPI application.

    Returns a fully wired app with HTTP routes, WebSocket, and
    /health reporting phase: "2" without secrets.
    """
    from app.agent.factory import create_tutorial_agent
    from app.agent.runtime import MockTutorialRuntime
    from app.api.events import InMemoryEventBus
    from app.api.server import create_app as create_server

    environ = os.environ
    profile = environ.get("APP_PROFILE", "tutorial")
    if profile == "showcase":
        # Showcase has an independent lazy configuration surface. Keep
        # unrelated legacy env values from failing startup before its gates run.
        settings = Phase2Settings.from_env({"APP_PROFILE": "showcase"})
    else:
        settings = Phase2Settings.from_env(environ)
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
        runtime = build_showcase_runtime(environ=environ, events=events)
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
