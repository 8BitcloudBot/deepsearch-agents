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
    from app.agent.runtime import MockTutorialRuntime
    from app.settings import Phase2Settings

    bundle = _bundle()
    runtime = MockTutorialRuntime(bundle, events)
    return create_app(
        settings=Phase2Settings(),
        bundle=bundle,
        runtime=runtime,
        events=events,
    )


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestHealth:
    @pytest.mark.asyncio
    async def test_phase_2(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["phase"] == "2"

    @pytest.mark.asyncio
    async def test_no_secrets(self, client):
        resp = await client.get("/health")
        data = resp.json()
        for v in data.values():
            if isinstance(v, str):
                assert "key" not in v.lower()


class TestTaskEndpoint:
    @pytest.mark.asyncio
    async def test_start_returns_202(self, client):
        resp = await client.post("/api/task", json={"query": "test"})
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "started"
        assert "thread_id" in data

    @pytest.mark.asyncio
    async def test_empty_query_422(self, client):
        resp = await client.post("/api/task", json={"query": ""})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_custom_thread_id(self, client):
        tid = "00000000-0000-4000-8000-0000000000a1"
        resp = await client.post(
            "/api/task",
            json={"query": "test", "thread_id": tid},
        )
        assert resp.status_code == 202
        assert resp.json()["thread_id"] == tid

    @pytest.mark.asyncio
    async def test_cancel_404(self, client):
        resp = await client.post(
            "/api/task/00000000-0000-4000-8000-000000000099/cancel"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_malformed_uuid_400(self, client):
        resp = await client.post("/api/task/not-a-uuid/cancel")
        assert resp.status_code == 400


class TestUploadEndpoint:
    @pytest.mark.asyncio
    async def test_upload_with_thread_id(self, client):
        tid = "00000000-0000-4000-8000-0000000000b1"
        resp = await client.post(
            "/api/upload",
            data={"thread_id": tid},
            files={"files": ("data.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "uploaded"
        assert data["thread_id"] == tid
        assert len(data["files"]) == 1
        assert data["files"][0]["filename"] == "data.txt"

    @pytest.mark.asyncio
    async def test_upload_unsafe_filename(self, client):
        tid = "00000000-0000-4000-8000-0000000000b2"
        resp = await client.post(
            "/api/upload",
            data={"thread_id": tid},
            files={"files": ("../secret.txt", b"bad", "text/plain")},
        )
        assert resp.status_code == 400


class TestFileEndpoints:
    @pytest.mark.asyncio
    async def test_files_empty(self, client):
        tid = "00000000-0000-4000-8000-0000000000c1"
        resp = await client.get(f"/api/files/{tid}")
        assert resp.status_code == 200
        assert resp.json()["files"] == []

    @pytest.mark.asyncio
    async def test_download_404(self, client):
        tid = "00000000-0000-4000-8000-0000000000c2"
        resp = await client.get(f"/api/download/{tid}/nope.txt")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_malformed_uuid_files_400(self, client):
        resp = await client.get("/api/files/not-uuid")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_malformed_uuid_download_400(self, client):
        resp = await client.get("/api/download/not-uuid/x.txt")
        assert resp.status_code == 400
