"""P4.5-3 showcase runtime integration with deterministic executors."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agent.runtime import RuntimeRequest  # noqa: E402
from app.api.context import SessionContext  # noqa: E402
from app.api.events import InMemoryEventBus  # noqa: E402
from app.api.tasks import TaskRegistry  # noqa: E402
from app.knowledge.contracts import EmbeddingDescriptor  # noqa: E402
from app.showcase.contracts import Limitation, SourceKind  # noqa: E402
from app.showcase.locator_adapters import (  # noqa: E402
    normalize_knowledge_chunk,
    normalize_mysql_row,
    normalize_tavily_hit,
    normalize_uploaded_span,
)
from app.showcase.runtime import ShowcaseResearchRuntime  # noqa: E402
from app.tools.files import SessionWorkspace  # noqa: E402

THREAD_ID = "aaaaaaaa-0000-4000-8000-000000000001"
FIXTURES = ROOT / "tests" / "fixtures" / "phase4_5"
TERMINAL_TYPES = {"task_completed", "task_cancelled", "task_failed"}


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _sources():
    return (
        normalize_tavily_hit(_fixture("web.json")),
        normalize_mysql_row(_fixture("mysql.json")),
        normalize_knowledge_chunk(_fixture("knowledge.json")),
        normalize_uploaded_span(_fixture("uploaded_file.json")),
    )


class RecordingExecutor:
    def __init__(self):
        self.calls = 0

    async def run(self, request, collector):
        self.calls += 1
        for source in _sources():
            collector.add(source, quote=source.display_text)
        return "Four-source research complete."


class FailingExecutor:
    async def run(self, request, collector):
        raise RuntimeError(
            "token=raw-secret from /Users/wxhu/private/provider-response.json"
        )


class BlockingExecutor:
    def __init__(self):
        self.entered = asyncio.Event()

    async def run(self, request, collector):
        self.entered.set()
        await asyncio.Event().wait()
        return "unreachable"


class RecordingDelivery:
    def __init__(self, limitations=()):
        self.calls = 0
        self.limitations = tuple(limitations)

    def deliver(self, request, result):
        from app.showcase.delivery import ShowcaseDeliveryResult

        self.calls += 1
        return ShowcaseDeliveryResult(
            ("live-citations.json", "showcase-report.md", "showcase-report.pdf"),
            self.limitations,
        )


def _request(tmp_path: Path) -> RuntimeRequest:
    workspace = SessionWorkspace.for_thread(
        thread_id=THREAD_ID,
        base_upload=str(tmp_path / "uploads"),
        base_output=str(tmp_path / "output"),
    )
    return RuntimeRequest(
        query="Compare research systems.",
        context=SessionContext(thread_id=THREAD_ID, workspace=workspace),
    )


@pytest.mark.asyncio
async def test_runtime_collects_four_sources_without_artifacts_or_terminal_events(
    tmp_path,
):
    events = InMemoryEventBus()
    executor = RecordingExecutor()
    runtime = ShowcaseResearchRuntime(events, executor)

    async with events.subscribe(THREAD_ID) as subscription:
        result = await runtime.run(_request(tmp_path))
        emitted = []
        while not subscription.queue.empty():
            emitted.append(subscription.queue.get_nowait())

    assert executor.calls == 1
    assert len(result.sources) == 4
    assert len(result.evidence) == 4
    assert result.artifacts == ()
    assert {event.type for event in emitted} == {"agent_started", "agent_completed"}
    assert not ({event.type for event in emitted} & TERMINAL_TYPES)


@pytest.mark.asyncio
async def test_runtime_delivers_after_collection_and_returns_artifacts(tmp_path):
    events = InMemoryEventBus()
    delivery = RecordingDelivery()
    runtime = ShowcaseResearchRuntime(events, RecordingExecutor(), delivery=delivery)

    result = await runtime.run(_request(tmp_path))

    assert delivery.calls == 1
    assert result.artifacts == (
        "live-citations.json",
        "showcase-report.md",
        "showcase-report.pdf",
    )


@pytest.mark.asyncio
async def test_delivery_limitation_is_preserved_and_registry_completes_once(tmp_path):
    events = InMemoryEventBus()
    limitation = Limitation(
        code="delivery-failed", source_kind=None, message="showcase delivery failed"
    )
    runtime = ShowcaseResearchRuntime(
        events, FailingExecutor(), delivery=RecordingDelivery((limitation,))
    )
    direct_result = await runtime.run(_request(tmp_path / "direct"))
    assert limitation in direct_result.limitations
    registry = TaskRegistry(
        runtime=runtime,
        events=events,
        base_upload=str(tmp_path / "uploads"),
        base_output=str(tmp_path / "output"),
    )

    async with events.subscribe(THREAD_ID) as subscription:
        registry.start("Research safely", thread_id=THREAD_ID)
        emitted = []
        while True:
            event = await asyncio.wait_for(subscription.queue.get(), timeout=2)
            emitted.append(event)
            if event.type in TERMINAL_TYPES:
                break

    terminals = [event for event in emitted if event.type in TERMINAL_TYPES]
    assert [event.type for event in terminals] == ["task_completed"]


@pytest.mark.asyncio
async def test_missing_executor_returns_limitation_and_makes_no_source_call(tmp_path):
    events = InMemoryEventBus()
    limitation = Limitation(
        code="model-unavailable",
        source_kind=None,
        message="showcase model configuration is unavailable",
    )
    runtime = ShowcaseResearchRuntime(events, None, (limitation,))

    result = await runtime.run(_request(tmp_path))

    assert result.sources == ()
    assert result.evidence == ()
    assert result.limitations == (limitation,)
    assert "live" not in result.answer.casefold()


@pytest.mark.asyncio
async def test_executor_failure_is_redacted_and_returns_agent_limitation(tmp_path):
    events = InMemoryEventBus()
    runtime = ShowcaseResearchRuntime(events, FailingExecutor())

    result = await runtime.run(_request(tmp_path))

    assert any(item.code == "agent-failed" for item in result.limitations)
    serialized = json.dumps(
        {
            "answer": result.answer,
            "limitations": [item.as_dict() for item in result.limitations],
        }
    )
    assert "raw-secret" not in serialized
    assert "/Users/wxhu/private" not in serialized


@pytest.mark.asyncio
async def test_task_registry_remains_sole_owner_of_one_terminal_event(tmp_path):
    events = InMemoryEventBus()
    runtime = ShowcaseResearchRuntime(events, FailingExecutor())
    registry = TaskRegistry(
        runtime=runtime,
        events=events,
        base_upload=str(tmp_path / "uploads"),
        base_output=str(tmp_path / "output"),
    )

    async with events.subscribe(THREAD_ID) as subscription:
        registry.start("Research safely", thread_id=THREAD_ID)
        emitted = []
        while True:
            event = await asyncio.wait_for(subscription.queue.get(), timeout=2)
            emitted.append(event)
            if event.type in TERMINAL_TYPES:
                break

    terminals = [event for event in emitted if event.type in TERMINAL_TYPES]
    assert len(terminals) == 1
    assert terminals[0].type == "task_completed"


@pytest.mark.asyncio
async def test_preflight_source_limitations_are_preserved_with_partial_results(
    tmp_path,
):
    events = InMemoryEventBus()
    limitation = Limitation(
        code="not-enabled",
        source_kind=SourceKind.KNOWLEDGE,
        message="source is not enabled",
    )
    runtime = ShowcaseResearchRuntime(events, RecordingExecutor(), (limitation,))

    result = await runtime.run(_request(tmp_path))

    assert limitation in result.limitations
    assert len(result.sources) == 4


@pytest.mark.asyncio
async def test_cancellation_propagates_to_registry_without_degraded_completion(
    tmp_path,
):
    events = InMemoryEventBus()
    executor = BlockingExecutor()
    runtime = ShowcaseResearchRuntime(events, executor)
    registry = TaskRegistry(
        runtime=runtime,
        events=events,
        base_upload=str(tmp_path / "uploads"),
        base_output=str(tmp_path / "output"),
    )

    async with events.subscribe(THREAD_ID) as subscription:
        registry.start("Research until cancelled", thread_id=THREAD_ID)
        await asyncio.wait_for(executor.entered.wait(), timeout=2)
        assert await registry.cancel(THREAD_ID) == "cancelled"
        emitted = []
        while not subscription.queue.empty():
            emitted.append(subscription.queue.get_nowait())

    terminals = [event for event in emitted if event.type in TERMINAL_TYPES]
    assert [event.type for event in terminals] == ["task_cancelled"]
    assert "agent_completed" not in {event.type for event in emitted}


def test_showcase_graph_uses_existing_roles_without_report_tools():
    from app.showcase.agent import create_showcase_agent
    from app.showcase.source_tools import ShowcaseToolSet

    class NamedTool:
        def __init__(self, name):
            self.name = name

    uploaded = NamedTool("showcase_read_uploaded_file")
    tools = ShowcaseToolSet(
        main_tools=(uploaded,),
        web_tools=(NamedTool("showcase_web_search"),),
        catalog_tools=(NamedTool("showcase_preview_table"),),
        knowledge_tools=(NamedTool("showcase_search_knowledge"),),
    )

    with patch("deepagents.create_deep_agent", return_value="showcase-graph") as create:
        graph = create_showcase_agent(object(), tools)

    assert graph == "showcase-graph"
    kwargs = create.call_args.kwargs
    assert kwargs["name"] == "showcase-research-agent"
    assert kwargs["tools"] == [uploaded]
    assert [worker["name"] for worker in kwargs["subagents"]] == [
        "web-research",
        "structured-data",
        "knowledge-base",
    ]
    assert "untrusted" in kwargs["system_prompt"].casefold()
    assert not {
        "generate_markdown_report_tool",
        "generate_pdf_report_tool",
    } & {tool.name for tool in kwargs["tools"]}


@pytest.mark.asyncio
async def test_showcase_executor_returns_only_final_non_empty_ai_message(tmp_path):
    from app.showcase.agent import DeepAgentsShowcaseExecutor
    from app.showcase.research import LiveSourceCollector

    class FakeGraph:
        async def astream(self, input_state, config, *, stream_mode):
            assert input_state["messages"][0]["content"] == "Compare research systems."
            assert config == {"configurable": {"thread_id": THREAD_ID}}
            assert stream_mode == "updates"
            yield {
                "worker": {"messages": [AIMessage(content="Worker internal result")]}
            }
            yield {"model": {"messages": [AIMessage(content="Planning next step")]}}
            yield {"tools": {"messages": [HumanMessage(content="raw source")]}}
            yield {"model": {"messages": [AIMessage(content="   ")]}}
            yield {"model": {"messages": [AIMessage(content="Final grounded answer.")]}}

    executor = DeepAgentsShowcaseExecutor(FakeGraph())
    answer = await executor.run(_request(tmp_path), LiveSourceCollector(THREAD_ID))

    assert answer == "Final grounded answer."
    assert "Worker internal result" not in answer
    assert "Planning next step" not in answer


def test_showcase_builder_is_lazy_and_fail_closed_without_opt_in():
    from app.main import build_showcase_runtime

    with (
        patch("langchain_openai.ChatOpenAI") as model,
        patch("app.providers.tavily.TavilyWebProvider") as web,
        patch("app.providers.mysql.MySQLCatalogProvider") as catalog,
        patch("app.knowledge.embeddings.FastEmbedEmbeddingAdapter") as embedder,
        patch("app.knowledge.qdrant_local.QdrantLocalKnowledgeIndex") as knowledge,
    ):
        runtime = build_showcase_runtime(environ={}, events=InMemoryEventBus())

    assert runtime._executor is None
    assert runtime._delivery is not None
    model.assert_not_called()
    web.assert_not_called()
    catalog.assert_not_called()
    embedder.assert_not_called()
    knowledge.assert_not_called()


def test_showcase_builder_constructs_only_declared_configured_provider():
    from app.main import build_showcase_runtime

    env = {
        "SHOWCASE_ENABLED": "1",
        "SHOWCASE_SOURCES": "web",
        "MODEL_NAME": "fake-model",
        "MODEL_API_KEY": "model-secret",  # pragma: allowlist secret
        "WEB_PROVIDER": "tavily",
        "TAVILY_API_KEY": "web-secret",  # pragma: allowlist secret
    }
    with (
        patch("langchain_openai.ChatOpenAI", return_value="fake-model") as model,
        patch(
            "app.providers.tavily.TavilyWebProvider", return_value="web-provider"
        ) as web,
        patch("app.providers.mysql.MySQLCatalogProvider") as catalog,
        patch("app.knowledge.embeddings.FastEmbedEmbeddingAdapter") as embedder,
        patch("app.knowledge.qdrant_local.QdrantLocalKnowledgeIndex") as knowledge,
        patch("deepagents.create_deep_agent", return_value="graph") as create_graph,
    ):
        runtime = build_showcase_runtime(environ=env, events=InMemoryEventBus())

    assert runtime._executor is not None
    model.assert_called_once_with(
        model="fake-model",
        api_key="model-secret",  # pragma: allowlist secret
        base_url=None,
    )
    web.assert_called_once_with(api_key="web-secret")  # pragma: allowlist secret
    catalog.assert_not_called()
    embedder.assert_not_called()
    knowledge.assert_not_called()
    create_graph.assert_called_once()


def test_showcase_builder_handles_model_constructor_failure_without_sources():
    from app.main import build_showcase_runtime

    env = {
        "SHOWCASE_ENABLED": "1",
        "SHOWCASE_SOURCES": "web,uploaded-file",
        "MODEL_NAME": "fake-model",
        "MODEL_API_KEY": "model-secret",  # pragma: allowlist secret
        "WEB_PROVIDER": "tavily",
        "TAVILY_API_KEY": "web-secret",  # pragma: allowlist secret
    }
    with (
        patch(
            "langchain_openai.ChatOpenAI",
            side_effect=RuntimeError("secret=raw path=/tmp/model.json"),
        ) as model,
        patch("app.providers.tavily.TavilyWebProvider") as web,
    ):
        runtime = build_showcase_runtime(environ=env, events=InMemoryEventBus())

    assert runtime._executor is None
    assert runtime._delivery is not None
    assert any(item.code == "model-unavailable" for item in runtime._limitations)
    model.assert_called_once()
    web.assert_not_called()


def test_showcase_builder_keeps_other_sources_when_knowledge_startup_fails():
    from app.main import build_showcase_runtime

    env = {
        "SHOWCASE_ENABLED": "1",
        "SHOWCASE_SOURCES": "web,knowledge,uploaded-file",
        "MODEL_NAME": "fake-model",
        "MODEL_API_KEY": "model-secret",  # pragma: allowlist secret
        "WEB_PROVIDER": "tavily",
        "TAVILY_API_KEY": "web-secret",  # pragma: allowlist secret
        "KNOWLEDGE_PROVIDER": "qdrant-local",
    }
    descriptor = EmbeddingDescriptor(
        provider="fastembed",
        model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        version="0.8.0",
        dimension=384,
    )
    with (
        patch("langchain_openai.ChatOpenAI", return_value="fake-model"),
        patch("app.providers.tavily.TavilyWebProvider", return_value="web-provider"),
        patch(
            "app.knowledge.embeddings.FastEmbedEmbeddingAdapter",
            return_value=type("Embedder", (), {"descriptor": descriptor})(),
        ),
        patch(
            "app.knowledge.qdrant_local.QdrantLocalKnowledgeIndex",
            side_effect=RuntimeError(
                "token=raw-secret path=/Users/private/knowledge-index"
            ),
        ),
        patch("deepagents.create_deep_agent", return_value="graph") as create_graph,
    ):
        runtime = build_showcase_runtime(environ=env, events=InMemoryEventBus())

    assert runtime._executor is not None
    knowledge_limitations = [
        (item.code, item.source_kind, item.message)
        for item in runtime._limitations
        if item.source_kind is SourceKind.KNOWLEDGE
    ]
    assert knowledge_limitations == [
        (
            "knowledge-unavailable",
            SourceKind.KNOWLEDGE,
            "knowledge collection is unavailable",
        )
    ]
    kwargs = create_graph.call_args.kwargs
    assert [tool.name for tool in kwargs["tools"]] == ["showcase_read_uploaded_file"]
    assert [worker["name"] for worker in kwargs["subagents"]] == ["web-research"]
    assembled = repr(kwargs) + repr(runtime._limitations)
    assert "raw-secret" not in assembled
    assert "/Users/private" not in assembled


def test_showcase_app_starts_with_invalid_legacy_phase2_environment(monkeypatch):
    monkeypatch.setenv("APP_PROFILE", "showcase")
    monkeypatch.setenv("SHOWCASE_ENABLED", "1")
    monkeypatch.setenv("SHOWCASE_SOURCES", "mysql")
    monkeypatch.setenv("CATALOG_PROVIDER", "mysql")
    monkeypatch.setenv("MYSQL_PORT", "not-a-port")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    from app.main import create_app

    assert create_app().title == "research-copilot-api"
