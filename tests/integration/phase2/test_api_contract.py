"""Integration: HTTP API contract tests."""

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


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_phase_2(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "2"
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_has_no_secrets(self, client):
        resp = await client.get("/health")
        data = resp.json()
        for key in data:
            assert "key" not in key.lower() or "api" not in key.lower()


class TestTaskEndpoint:
    @pytest.mark.asyncio
    async def test_task_start_returns_202(self, client):
        resp = await client.post("/api/task", json={"query": "test query"})
        assert resp.status_code == 202
        data = resp.json()
        assert "thread_id" in data
        assert data["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_empty_query_rejected(self, client):
        resp = await client.post("/api/task", json={"query": ""})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_returns_404(self, client):
        resp = await client.post(
            "/api/task/00000000-0000-4000-8000-000000000099/cancel"
        )
        assert resp.status_code == 404


class TestUploadEndpoint:
    @pytest.mark.asyncio
    async def test_upload_txt(self, client):
        resp = await client.post(
            "/api/upload",
            files={"file": ("test.txt", b"hello world", "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "test.txt"
        assert data["size"] > 0

    @pytest.mark.asyncio
    async def test_upload_unsafe_filename(self, client):
        resp = await client.post(
            "/api/upload",
            files={"file": ("../secret.txt", b"bad", "text/plain")},
        )
        assert resp.status_code in (400, 422)


class TestFileEndpoints:
    @pytest.mark.asyncio
    async def test_files_empty_for_unknown_thread(self, client):
        resp = await client.get(
            "/api/files",
            params={"thread_id": "00000000-0000-4000-8000-000000000099"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["files"] == []

    @pytest.mark.asyncio
    async def test_download_missing_returns_404(self, client):
        resp = await client.get(
            "/api/download",
            params={
                "thread_id": "00000000-0000-4000-8000-000000000099",
                "path": "nonexistent.txt",
            },
        )
        assert resp.status_code == 404
