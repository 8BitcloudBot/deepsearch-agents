"""E2E: Full tutorial closure — upload, task, WebSocket, download."""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.events import InMemoryEventBus
from app.api.server import create_app
from app.providers.contracts import ProviderBundle
from app.providers.mock import (
    MockCatalogProvider,
    MockKnowledgeProvider,
    MockWebProvider,
)


def _bundle():
    return ProviderBundle(
        web=MockWebProvider(),
        catalog=MockCatalogProvider(),
        knowledge=MockKnowledgeProvider(),
        web_mode="mock",
        catalog_mode="mock",
        knowledge_mode="mock",
    )


@pytest.fixture
def events():
    return InMemoryEventBus()


@pytest.fixture
def app(events):
    bundle = _bundle()
    from app.agent.runtime import MockTutorialRuntime

    runtime = MockTutorialRuntime(bundle, events)
    from app.settings import Phase2Settings

    settings = Phase2Settings()
    return create_app(settings=settings, bundle=bundle, runtime=runtime, events=events)


@pytest.mark.asyncio
async def test_full_mock_closure(app, events):
    """Upload constraints.md, start task, collect events, list/download reports."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Upload constraints
        up_resp = await client.post(
            "/api/upload",
            files={
                "file": (
                    "constraints.md",
                    b"# Constraint\n\nKeep it short.",
                    "text/markdown",
                )
            },
        )
        assert up_resp.status_code == 200

        # 2. Start task
        task_resp = await client.post(
            "/api/task",
            json={"query": "research aspirin and compare sources"},
        )
        assert task_resp.status_code == 202
        tid = task_resp.json()["thread_id"]

        # 3. Collect events via event bus subscription
        terminal_types = {
            "task_completed",
            "task_cancelled",
            "task_failed",
        }
        async with events.subscribe(tid) as sub:
            collected: list = []
            deadline = asyncio.get_event_loop().time() + 10
            while True:
                try:
                    evt = await asyncio.wait_for(
                        sub.queue.get(),
                        timeout=max(0, deadline - asyncio.get_event_loop().time()),
                    )
                    collected.append(evt)
                    if evt.type in terminal_types:
                        break
                except TimeoutError:
                    break

        # 4. Assert all three provider tool names occurred
        tool_names = {
            e.data.get("tool_name") for e in collected if "tool_name" in e.data
        }
        assert "internet_search" in tool_names, f"Missing web: {tool_names}"
        assert tool_names & {
            "list_sql_tables",
            "preview_table",
            "execute_readonly_query",
        }, f"Missing catalog: {tool_names}"
        assert tool_names & {
            "list_knowledge_assistants",
            "ask_knowledge_assistant",
        }, f"Missing knowledge: {tool_names}"

        # 5. List files
        files_resp = await client.get("/api/files", params={"thread_id": tid})
        assert files_resp.status_code == 200
        flist = files_resp.json()["files"]
        fnames = {f["name"] for f in flist}
        assert "tutorial-report.md" in fnames
        assert "tutorial-report.pdf" in fnames

        # 6. Download Markdown report
        dl_resp = await client.get(
            "/api/download",
            params={"thread_id": tid, "path": "tutorial-report.md"},
        )
        assert dl_resp.status_code == 200
        content = dl_resp.text
        assert "mock" in content.lower() or "Provider" in content
        assert len(content) > 20
