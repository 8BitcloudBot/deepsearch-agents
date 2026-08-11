"""P4.5-4 live citation HTTP delivery contracts."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.events import InMemoryEventBus
from app.api.server import create_app
from app.settings import Phase2Settings
from app.showcase.delivery import ShowcaseCitationDelivery
from app.showcase.locator_adapters import (
    normalize_knowledge_chunk,
    normalize_mysql_row,
    normalize_tavily_hit,
    normalize_uploaded_span,
)
from app.showcase.runtime import ShowcaseResearchRuntime

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "phase4_5"
THREAD_ID = "aaaaaaaa-0000-4000-8000-000000000101"
OTHER_THREAD_ID = "bbbbbbbb-0000-4000-8000-000000000102"
TERMINAL_TYPES = {"task_completed", "task_cancelled", "task_failed"}
UPLOAD_MEDIA_TYPES = {
    "notes.txt": "text/plain",
    "notes.md": "text/markdown",
    "paper.pdf": "application/pdf",
    "brief.docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
    "data.xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class DeterministicExecutor:
    async def run(self, request, collector):
        collector.add(
            normalize_tavily_hit(_fixture("web.json")),
            quote="Web evidence supports the answer.",
        )
        collector.add(
            normalize_mysql_row(_fixture("mysql.json")),
            quote="Catalog evidence supports the answer.",
        )
        collector.add(
            normalize_knowledge_chunk(_fixture("knowledge.json")),
            quote="Knowledge evidence supports the answer.",
        )
        collector.add(
            normalize_uploaded_span(_fixture("uploaded_file.json")),
            quote="Uploaded evidence supports the answer.",
        )
        return "First research paragraph.\n\nSecond research paragraph."


async def _wait_for_task(client: AsyncClient, events: InMemoryEventBus) -> list:
    async with events.subscribe(THREAD_ID) as subscription:
        response = await client.post(
            "/api/task", json={"query": "showcase", "thread_id": THREAD_ID}
        )
        assert response.status_code == 202
        emitted = []
        while True:
            event = await asyncio.wait_for(subscription.queue.get(), timeout=5)
            emitted.append(event)
            if event.type in TERMINAL_TYPES:
                return emitted


@pytest.fixture
def app_and_events(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    events = InMemoryEventBus()
    runtime = ShowcaseResearchRuntime(
        events,
        DeterministicExecutor(),
        delivery=ShowcaseCitationDelivery(events),
    )
    return create_app(settings=Phase2Settings(), runtime=runtime, events=events), events


@pytest.mark.asyncio
async def test_live_citation_endpoint_and_artifact_downloads(app_and_events):
    app, events = app_and_events
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        emitted = await _wait_for_task(ac, events)

        response = await ac.get("/api/live-citations", params={"thread_id": THREAD_ID})
        assert response.status_code == 200
        payload = response.json()
        assert payload["thread_id"] == THREAD_ID
        document = payload["document"]
        assert document["schema_version"] == "2.0.0"
        assert document["claims"][0]["evidence_ids"]

        listing = await ac.get("/api/files", params={"thread_id": THREAD_ID})
        names = {item["name"] for item in listing.json()["files"]}
        assert names >= {
            "live-citations.json",
            "showcase-report.md",
            "showcase-report.pdf",
        }

        markdown = await ac.get(
            "/api/download",
            params={"thread_id": THREAD_ID, "path": "showcase-report.md"},
        )
        assert markdown.status_code == 200
        assert markdown.headers["content-type"].startswith("text/markdown")
        assert "[claim-1]" in markdown.text

        pdf = await ac.get(
            "/api/download",
            params={"thread_id": THREAD_ID, "path": "showcase-report.pdf"},
        )
        assert pdf.status_code == 200
        assert pdf.headers["content-type"].startswith("application/pdf")
        assert pdf.content[:4] == b"%PDF"

        assert [
            event.type
            for event in emitted
            if event.type.startswith("citation") or event.type == "artifact_created"
        ] == [
            "citation_started",
            "artifact_created",
            "artifact_created",
            "artifact_created",
            "citation_completed",
        ]
        assert [event.type for event in emitted if event.type in TERMINAL_TYPES] == [
            "task_completed"
        ]


@pytest.mark.asyncio
async def test_live_citation_is_thread_scoped_and_old_citations_contract_survives(
    app_and_events,
):
    app, events = app_and_events
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        await _wait_for_task(ac, events)

        missing = await ac.get(
            "/api/live-citations", params={"thread_id": OTHER_THREAD_ID}
        )
        assert missing.status_code == 404
        malformed = await ac.get("/api/live-citations", params={"thread_id": "bad"})
        assert malformed.status_code == 400

        from app.tools.files import SessionWorkspace

        workspace = SessionWorkspace.for_thread(
            thread_id=THREAD_ID, base_upload="updated", base_output="output"
        )
        phase4_report = {
            "schema_version": "1.0.0",
            "partitions": {"rule/offline": {}},
            "report_fingerprint": "a" * 64,
        }
        (workspace.output_dir / "citation-report.json").write_text(
            json.dumps(phase4_report), encoding="utf-8"
        )
        old = await ac.get("/api/citations", params={"thread_id": THREAD_ID})
        assert old.status_code == 200
        assert old.json() == {"thread_id": THREAD_ID, "report": phase4_report}


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "media_type"), UPLOAD_MEDIA_TYPES.items())
async def test_uploaded_source_route_returns_current_thread_file_with_safe_media_type(
    app_and_events, name, media_type
):
    app, _ = app_and_events
    from app.tools.files import SessionWorkspace

    workspace = SessionWorkspace.for_thread(
        thread_id=THREAD_ID, base_upload="updated", base_output="output"
    )
    content = f"fixture for {name}".encode()
    workspace.resolve_upload(name).write_bytes(content)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get(f"/api/threads/{THREAD_ID}/uploads/{name}")

    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"].startswith(media_type)
    assert Path.cwd().as_posix() not in response.text
    assert "filename=" in response.headers["content-disposition"]
    assert (
        str(workspace.upload_dir.resolve())
        not in response.headers["content-disposition"]
    )


@pytest.mark.asyncio
async def test_uploaded_source_route_is_thread_scoped_and_rejects_missing_targets(
    app_and_events,
):
    app, _ = app_and_events
    from app.tools.files import SessionWorkspace

    current = SessionWorkspace.for_thread(
        thread_id=THREAD_ID, base_upload="updated", base_output="output"
    )
    other = SessionWorkspace.for_thread(
        thread_id=OTHER_THREAD_ID, base_upload="updated", base_output="output"
    )
    other.resolve_upload("foreign.txt").write_text("foreign", encoding="utf-8")
    current.resolve_upload("folder.txt").mkdir()
    current.resolve_upload("unsupported.csv").write_text("value", encoding="utf-8")

    outside = Path("outside.txt")
    outside.write_text("outside", encoding="utf-8")
    current.resolve_upload("link.txt").symlink_to(outside.resolve())

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        responses = {
            "missing": await ac.get(f"/api/threads/{THREAD_ID}/uploads/missing.txt"),
            "foreign": await ac.get(f"/api/threads/{THREAD_ID}/uploads/foreign.txt"),
            "directory": await ac.get(f"/api/threads/{THREAD_ID}/uploads/folder.txt"),
            "symlink": await ac.get(f"/api/threads/{THREAD_ID}/uploads/link.txt"),
            "unsupported": await ac.get(
                f"/api/threads/{THREAD_ID}/uploads/unsupported.csv"
            ),
        }

    assert {key: response.status_code for key, response in responses.items()} == {
        "missing": 404,
        "foreign": 404,
        "directory": 404,
        "symlink": 404,
        "unsupported": 404,
    }
    assert all("outside" not in response.text for response in responses.values())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/threads/not-a-uuid/uploads/notes.txt",
        f"/api/threads/{THREAD_ID}/uploads/..%2Fnotes.txt",
        f"/api/threads/{THREAD_ID}/uploads/%2Ftmp%2Fnotes.txt",
        f"/api/threads/{THREAD_ID}/uploads/%5Ctmp%5Cnotes.txt",
    ],
)
async def test_uploaded_source_route_rejects_malformed_identity_and_unsafe_names(
    app_and_events, path
):
    app, _ = app_and_events
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get(path)

    assert response.status_code in {400, 404}
    assert "/Users/" not in response.text
    assert "outside" not in response.text
