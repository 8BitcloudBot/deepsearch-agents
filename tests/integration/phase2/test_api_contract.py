"""Integration: HTTP API contract tests."""

import pytest
from starlette.testclient import TestClient

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
def client(events):
    from app.agent.runtime import MockTutorialRuntime
    from app.settings import Phase2Settings

    bundle = _bundle()
    runtime = MockTutorialRuntime(bundle, events)
    app = create_app(
        settings=Phase2Settings(),
        bundle=bundle,
        runtime=runtime,
        events=events,
    )
    return TestClient(app)


class TestHealth:
    def test_phase_2(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["phase"] == "2"


class TestTaskEndpoint:
    def test_start_returns_202(self, client):
        resp = client.post("/api/task", json={"query": "test"})
        assert resp.status_code == 202
        assert resp.json()["status"] == "started"

    def test_empty_query_422(self, client):
        resp = client.post("/api/task", json={"query": ""})
        assert resp.status_code == 422

    def test_custom_thread_id(self, client):
        tid = "00000000-0000-4000-8000-0000000000a1"
        resp = client.post("/api/task", json={"query": "test", "thread_id": tid})
        assert resp.status_code == 202
        assert resp.json()["thread_id"] == tid

    def test_cancel_404(self, client):
        resp = client.post("/api/task/00000000-0000-4000-8000-000000000099/cancel")
        assert resp.status_code == 404

    def test_malformed_uuid_400(self, client):
        resp = client.post("/api/task/not-a-uuid/cancel")
        assert resp.status_code == 400

    def test_thread_id_malformed_400(self, client):
        resp = client.post(
            "/api/task",
            json={"query": "test", "thread_id": "not-a-uuid"},
        )
        assert resp.status_code == 422


class TestUploadEndpoint:
    def test_upload_with_thread_id(self, client):
        tid = "00000000-0000-4000-8000-0000000000b1"
        resp = client.post(
            "/api/upload",
            data={"thread_id": tid},
            files={"files": ("data.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "uploaded"
        assert data["thread_id"] == tid
        assert len(data["files"]) == 1
        assert data["files"][0]["name"] == "data.txt"

    def test_upload_unsafe_filename(self, client):
        tid = "00000000-0000-4000-8000-0000000000b2"
        resp = client.post(
            "/api/upload",
            data={"thread_id": tid},
            files={"files": ("../secret.txt", b"bad", "text/plain")},
        )
        assert resp.status_code == 400

    def test_upload_multiple_files(self, client):
        tid = "00000000-0000-4000-8000-0000000000b3"
        resp = client.post(
            "/api/upload",
            data={"thread_id": tid},
            files=[
                ("files", ("a.txt", b"aaa", "text/plain")),
                ("files", ("b.txt", b"bbb", "text/plain")),
            ],
        )
        assert resp.status_code == 200
        assert len(resp.json()["files"]) == 2


class TestFileEndpoints:
    def test_files_empty(self, client):
        tid = "00000000-0000-4000-8000-0000000000c1"
        resp = client.get("/api/files", params={"thread_id": tid})
        assert resp.status_code == 200
        assert resp.json()["files"] == []

    def test_download_404(self, client):
        tid = "00000000-0000-4000-8000-0000000000c2"
        resp = client.get(
            "/api/download",
            params={"thread_id": tid, "path": "nope.txt"},
        )
        assert resp.status_code == 404

    def test_malformed_uuid_files_400(self, client):
        resp = client.get("/api/files", params={"thread_id": "not-uuid"})
        assert resp.status_code == 400

    def test_malformed_uuid_download_400(self, client):
        resp = client.get(
            "/api/download",
            params={"thread_id": "not-uuid", "path": "x.txt"},
        )
        assert resp.status_code == 400
