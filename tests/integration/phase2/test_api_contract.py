"""Integration: HTTP API contract tests."""

import asyncio
import os
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app.agent.runtime import RuntimeResult
from app.api.events import InMemoryEventBus
from app.api.server import create_app
from app.providers.contracts import ProviderBundle
from app.providers.mock import (
    MockCatalogProvider,
    MockKnowledgeProvider,
    MockWebProvider,
)
from app.tools.files import MAX_FILE_SIZE_BYTES, SessionWorkspace

BAD_UUIDS = [
    "bad",
    "00000000-0000-4000-8000",
    "00000000-0000-4000-8000-0000000000zz",
    "00000000-0000-4000-8000-0000000000FF",
    "00000000-0000-4000-8000-0000000000ffff",
]


class _BlockingRuntime:
    """Runtime that blocks until released — keeps a task deterministically active."""

    def __init__(self):
        self._gate = asyncio.Event()

    async def run(self, request):
        await self._gate.wait()
        return RuntimeResult(answer="ok", artifacts=())

    def release(self):
        self._gate.set()


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

    def test_local_frontend_origin_is_allowed_for_health(self, client):
        response = client.options(
            "/health",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert (
            response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
        )


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

    @pytest.mark.parametrize(
        "tid",
        [
            "00000000-0000-4000-8000-0000000000e5",
            "00000000-0000-4000-8000-0000000000e6",
            "00000000-0000-4000-8000-0000000000e7",
        ],
    )
    def test_cancel_unknown_thread_404(self, client, tid):
        r = client.post(f"/api/task/{tid}/cancel")
        assert r.status_code == 404
        assert r.json()["detail"] == "task not found"

    @pytest.mark.parametrize("endpoint", ["cancel", "upload", "list", "download"])
    @pytest.mark.parametrize("bad", BAD_UUIDS)
    def test_malformed_uuid_rejected_400(self, client, endpoint, bad):
        if endpoint == "cancel":
            r = client.post(f"/api/task/{bad}/cancel")
        elif endpoint == "upload":
            r = client.post(
                "/api/upload",
                data={"thread_id": bad},
                files={"files": ("a.txt", b"x", "text/plain")},
            )
        elif endpoint == "list":
            r = client.get("/api/files", params={"thread_id": bad})
        else:
            r = client.get("/api/download", params={"thread_id": bad, "path": "a.txt"})
        assert r.status_code == 400
        assert "UUID" in r.json()["detail"]

    def test_duplicate_start_409_then_restart_after_cancel(self):
        from app.settings import Phase2Settings

        runtime = _BlockingRuntime()
        app = create_app(
            settings=Phase2Settings(),
            bundle=_bundle(),
            runtime=runtime,
            events=InMemoryEventBus(),
        )
        tid = "00000000-0000-4000-8000-0000000000f1"
        # The with-block keeps one event loop alive across requests, so the
        # started task stays provably active when the duplicate arrives.
        with TestClient(app) as tc:
            assert (
                tc.post("/api/task", json={"query": "q", "thread_id": tid}).status_code
                == 202
            )
            dup = tc.post("/api/task", json={"query": "q2", "thread_id": tid})
            assert dup.status_code == 409
            assert "already running" in dup.json()["detail"]
            cancel = tc.post(f"/api/task/{tid}/cancel")
            assert cancel.status_code == 200
            assert cancel.json()["status"] == "cancelled"
            # The same thread_id may start again only after the registry
            # freed it.
            assert (
                tc.post("/api/task", json={"query": "q3", "thread_id": tid}).status_code
                == 202
            )
            assert tc.post(f"/api/task/{tid}/cancel").json()["status"] == "cancelled"
            runtime.release()


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

    @pytest.mark.parametrize(
        ("name", "content", "status"),
        [
            ("evil.exe", b"MZ\x90\x00", 400),
            ("legacy.doc", b"legacy", 400),
            ("notes.txt", b"\xff\xfe not utf-8", 400),
            ("sheet.docx", b"plain text, not a zip", 400),
            # Backslash traversal reaches the endpoint intact (only drive
            # prefixes like C:\ are normalized away by the multipart layer).
            ("..\\..\\secret.txt", b"x", 400),
            # httpx omits the filename attribute for an empty name, so
            # FastAPI's File validation rejects the part with 422.
            ("", b"x", 422),
        ],
    )
    def test_upload_rejected(self, client, name, content, status):
        tid = "00000000-0000-4000-8000-0000000000f6"
        r = client.post(
            "/api/upload",
            data={"thread_id": tid},
            files={"files": (name, content, "text/plain")},
        )
        assert r.status_code == status

    def test_upload_oversized_413(self, client):
        tid = "00000000-0000-4000-8000-0000000000f7"
        r = client.post(
            "/api/upload",
            data={"thread_id": tid},
            files={
                "files": (
                    "big.md",
                    b"x" * (MAX_FILE_SIZE_BYTES + 1),
                    "text/plain",
                )
            },
        )
        assert r.status_code == 413


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

    @pytest.mark.parametrize(
        "path",
        [
            "../secret.txt",
            "../../../etc/passwd",
            "/etc/passwd",
            "nested/file.txt",
            "a\\b.txt",
            "..",
            ".",
            "",
            "   ",
        ],
    )
    def test_download_unsafe_path_400(self, client, path):
        tid = "00000000-0000-4000-8000-0000000000f8"
        r = client.get("/api/download", params={"thread_id": tid, "path": path})
        assert r.status_code == 400
        assert r.json()["detail"] == "invalid path"

    def test_cross_thread_list_and_download_isolation(self, client):
        """Thread B can neither list nor download thread A's output files."""
        tid_a = "00000000-0000-4000-8000-0000000000f3"
        tid_b = "00000000-0000-4000-8000-0000000000f4"
        ws_a = SessionWorkspace.for_thread(
            thread_id=tid_a, base_upload="updated", base_output="output"
        )
        (ws_a.output_dir / "only_a.txt").write_text("secret-a")

        listed = client.get("/api/files", params={"thread_id": tid_a})
        assert listed.status_code == 200
        assert [f["name"] for f in listed.json()["files"]] == ["only_a.txt"]

        got = client.get(
            "/api/download", params={"thread_id": tid_a, "path": "only_a.txt"}
        )
        assert got.status_code == 200
        assert got.content == b"secret-a"

        other_list = client.get("/api/files", params={"thread_id": tid_b})
        assert other_list.status_code == 200
        assert other_list.json()["files"] == []

        other_dl = client.get(
            "/api/download", params={"thread_id": tid_b, "path": "only_a.txt"}
        )
        assert other_dl.status_code == 404

    def test_download_rejects_symlink_escape(self, client, tmp_path):
        tid = "00000000-0000-4000-8000-0000000000f9"
        ws = SessionWorkspace.for_thread(
            thread_id=tid, base_upload="updated", base_output="output"
        )
        outside = tmp_path / "outside_secret.txt"
        outside.write_text("secret")
        link = ws.output_dir / "link.txt"
        link.unlink(missing_ok=True)  # CWD-scoped workspace persists across runs
        os.symlink(str(outside), link)
        r = client.get("/api/download", params={"thread_id": tid, "path": "link.txt"})
        assert r.status_code == 400

    def test_error_details_never_contain_resolved_paths(self, client):
        leaked = {str(Path("updated").resolve()), str(Path("output").resolve())}
        tid = "00000000-0000-4000-8000-0000000000fa"
        responses = [
            client.post("/api/task/x/cancel"),
            client.post(f"/api/task/{tid}/cancel"),
            client.post(
                "/api/upload",
                data={"thread_id": tid},
                files={"files": ("fake.pdf", b"nope", "text/plain")},
            ),
            client.get("/api/files", params={"thread_id": "bad"}),
            client.get("/api/download", params={"thread_id": tid, "path": "../x.txt"}),
            client.get("/api/download", params={"thread_id": tid, "path": "x.txt"}),
        ]
        for r in responses:
            assert r.status_code >= 400, r.text
            for marker in leaked:
                assert marker not in r.text, (marker, r.text)
