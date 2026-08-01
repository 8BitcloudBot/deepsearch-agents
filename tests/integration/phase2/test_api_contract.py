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
        assert client.get("/health").json()["phase"] == "2"


class TestTask:
    def test_start_202(self, client):
        r = client.post("/api/task", json={"query": "t"})
        assert r.status_code == 202
        assert r.json()["status"] == "started"

    def test_empty_query_422(self, client):
        assert client.post("/api/task", json={"query": ""}).status_code == 422

    def test_thread_id_malformed_422(self, client):
        r = client.post("/api/task", json={"query": "t", "thread_id": "bad"})
        assert r.status_code == 422

    def test_cancel_404(self, client):
        r = client.post("/api/task/00000000-0000-4000-8000-000000000099/cancel")
        assert r.status_code == 404

    def test_malformed_uuid_400(self, client):
        assert client.post("/api/task/x/cancel").status_code == 400


class TestUpload:
    def test_ok(self, client):
        tid = "00000000-0000-4000-8000-0000000000b1"
        r = client.post(
            "/api/upload",
            data={"thread_id": tid},
            files={"files": ("a.txt", b"hi", "text/plain")},
        )
        assert r.status_code == 200
        assert r.json()["files"][0]["name"] == "a.txt"

    def test_multi(self, client):
        tid = "00000000-0000-4000-8000-0000000000b2"
        r = client.post(
            "/api/upload",
            data={"thread_id": tid},
            files=[
                ("files", ("a.txt", b"a", "text/plain")),
                ("files", ("b.txt", b"b", "text/plain")),
            ],
        )
        assert r.status_code == 200
        assert len(r.json()["files"]) == 2

    def test_extension_mismatch(self, client):
        tid = "00000000-0000-4000-8000-0000000000b3"
        r = client.post(
            "/api/upload",
            data={"thread_id": tid},
            files={"files": ("fake.pdf", b"not pdf", "text/plain")},
        )
        assert r.status_code == 400

    def test_unsafe_name(self, client):
        tid = "00000000-0000-4000-8000-0000000000b4"
        r = client.post(
            "/api/upload",
            data={"thread_id": tid},
            files={"files": ("../secret.txt", b"x", "text/plain")},
        )
        assert r.status_code == 400


class TestFiles:
    def test_empty(self, client):
        r = client.get(
            "/api/files", params={"thread_id": "00000000-0000-4000-8000-0000000000c1"}
        )
        assert r.json()["files"] == []

    def test_download_404(self, client):
        r = client.get(
            "/api/download",
            params={
                "thread_id": "00000000-0000-4000-8000-0000000000c2",
                "path": "nope.txt",
            },
        )
        assert r.status_code == 404

    def test_malformed_uuid_400(self, client):
        assert client.get("/api/files", params={"thread_id": "bad"}).status_code == 400

    def test_cross_thread_isolation(self, client):
        """Files from thread A don't appear in thread B."""
        tid_a = "00000000-0000-4000-8000-0000000000c3"
        tid_b = "00000000-0000-4000-8000-0000000000c4"
        client.post(
            "/api/upload",
            data={"thread_id": tid_a},
            files={"files": ("only_a.txt", b"a", "text/plain")},
        )
        r = client.get("/api/files", params={"thread_id": tid_b})
        assert r.status_code == 200
        assert r.json()["files"] == []
