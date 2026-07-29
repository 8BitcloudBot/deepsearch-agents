"""Real-model smoke test — gated, never silently skipped as mock."""

import os
from pathlib import Path

import pytest

from app.agent.factory import create_tutorial_agent
from app.agent.runtime import DeepAgentsTutorialRuntime, RuntimeRequest
from app.api.context import SessionContext
from app.api.events import InMemoryEventBus
from app.providers.contracts import ProviderBundle
from app.providers.mock import (
    MockCatalogProvider,
    MockKnowledgeProvider,
    MockWebProvider,
)
from app.tools.files import SessionWorkspace

pytestmark = pytest.mark.skipif(
    not (
        os.environ.get("PHASE2_REAL_MODEL_SMOKE") == "1"
        and os.environ.get("MODEL_API_KEY")
    ),
    reason="Set PHASE2_REAL_MODEL_SMOKE=1 and MODEL_API_KEY to run real model smoke",
)

THREAD_ID = "00000000-0000-4000-8000-999999999999"


def _bundle() -> ProviderBundle:
    return ProviderBundle(
        web=MockWebProvider(),
        catalog=MockCatalogProvider(),
        knowledge=MockKnowledgeProvider(),
        web_mode="mock",
        catalog_mode="mock",
        knowledge_mode="mock",
    )


@pytest.fixture
def bundle():
    return _bundle()


@pytest.fixture
def events():
    return InMemoryEventBus()


@pytest.fixture
def workspace(tmp_path: Path):
    return SessionWorkspace.for_thread(
        thread_id=THREAD_ID,
        base_upload=str(tmp_path / "updated"),
        base_output=str(tmp_path / "output"),
    )


@pytest.fixture
def context(workspace):
    return SessionContext(thread_id=THREAD_ID, workspace=workspace)


@pytest.mark.asyncio
async def test_real_model_produces_artifacts(bundle, events, workspace, context):
    """Use mock providers + real model; assert artifacts are produced.

    Never silently switches to MockTutorialRuntime.
    """
    # Explicit: we are testing DeepAgentsTutorialRuntime, not MockTutorialRuntime
    assert DeepAgentsTutorialRuntime is not None  # import check

    # Construct a real OpenAI-compatible model using env vars
    api_key = os.environ["MODEL_API_KEY"]
    base_url = os.environ.get("MODEL_BASE_URL") or None
    model_name = os.environ.get("MODEL_NAME", "gpt-4.1-mini")

    from langchain_openai import ChatOpenAI

    model = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
    )

    graph = create_tutorial_agent(model, bundle, events, lambda tid: None)
    assert graph is not None

    runtime = DeepAgentsTutorialRuntime(
        graph=graph,
        bundle=bundle,
        events=events,
    )

    async with events.subscribe(THREAD_ID) as sub:
        result = await runtime.run(
            RuntimeRequest("list all drug tables and summarize the catalog", context)
        )
        emitted = []
        while not sub.queue.empty():
            emitted.append(sub.queue.get_nowait())

    # Must produce answer text
    assert isinstance(result.answer, str)
    assert len(result.answer) > 10

    # Must produce both artifacts
    assert "tutorial-report.md" in result.artifacts
    assert "tutorial-report.pdf" in result.artifacts

    # Must have emitted events
    event_types = {e.type for e in emitted}
    assert "agent_started" in event_types
    assert "agent_completed" in event_types

    # Files exist
    md = workspace.resolve_output("tutorial-report.md")
    pdf = workspace.resolve_output("tutorial-report.pdf")
    assert md.exists()
    assert pdf.exists()
