"""Integration: GET /api/citations and thread-scoped citation artifacts (P4-5).

After an agent-research task, the thread exposes validated citation results:

* ``GET /api/citations?thread_id=<uuid>`` returns the deterministic report.
* ``citation-report.json`` / ``citation-partitions.jsonl`` live in the
  thread's output dir and are listed/downloadable through the existing
  ``/api/files`` and ``/api/download`` endpoints by their relative names.

Unknown/foreign threads return 404; malformed UUIDs return 400. The tutorial
profile never produces citation results.
"""

import asyncio
import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.events import InMemoryEventBus
from app.api.server import create_app
from app.research.runtime import AgentResearchRuntime
from app.settings import Phase2Settings

TID = "00000000-0000-4000-8000-000000000511"
TID_OTHER = "00000000-0000-4000-8000-000000000512"
TID_TUTORIAL = "00000000-0000-4000-8000-000000000513"
TERMINAL_TYPES = {"task_completed", "task_cancelled", "task_failed"}
CITATION_TYPES = {"citation_started", "citation_completed"}

CITATION_REPORT_FILENAME = "citation-report.json"
CITATION_PARTITIONS_FILENAME = "citation-partitions.jsonl"

BAD_UUIDS = [
    "bad",
    "00000000-0000-4000-8000",
    "00000000-0000-4000-8000-0000000005zz",
]


@pytest.fixture
def events():
    return InMemoryEventBus()


async def _start_and_wait(ac, events, tid, query="Compare agent orchestration."):
    async with events.subscribe(tid) as sub:
        response = await ac.post("/api/task", json={"query": query, "thread_id": tid})
        assert response.status_code == 202
        emitted = []
        while True:
            event = await asyncio.wait_for(sub.queue.get(), timeout=10.0)
            emitted.append(event)
            if event.type in TERMINAL_TYPES:
                return emitted


def _research_app(events):
    return create_app(
        settings=Phase2Settings(), runtime=AgentResearchRuntime(events), events=events
    )


@pytest.mark.asyncio
async def test_get_citations_returns_validated_report(events, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _research_app(events)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        emitted = await _start_and_wait(ac, events, TID)

        response = await ac.get("/api/citations", params={"thread_id": TID})
        assert response.status_code == 200
        body = response.json()
        assert body["thread_id"] == TID
        report = body["report"]
        assert report["schema_version"] == "1.0.0"
        assert set(report["partitions"]) == {
            "rule/offline",
            "semantic/mock",
            "semantic/real",
        }
        assert len(report["report_fingerprint"]) == 64
        assert report["provenance"]["dataset_id"] == "seed-10-v1"
        assert report["provenance"]["corpus_id"] == "agent-research-corpus-v1"

        # The success path still emits exactly one terminal event.
        terminals = [e for e in emitted if e.type in TERMINAL_TYPES]
        assert len(terminals) == 1
        assert terminals[0].type == "task_completed"


@pytest.mark.asyncio
async def test_foreign_thread_rejected_and_isolated(events, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _research_app(events)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        await _start_and_wait(ac, events, TID)

        # A thread that never ran has no citation results.
        response = await ac.get("/api/citations", params={"thread_id": TID_OTHER})
        assert response.status_code == 404
        assert "citation" in response.json()["detail"]

        # Thread A's results are only visible under thread A.
        own = await ac.get("/api/citations", params={"thread_id": TID})
        assert own.status_code == 200

        # Malformed UUIDs are rejected before any lookup.
        for bad in BAD_UUIDS:
            response = await ac.get("/api/citations", params={"thread_id": bad})
            assert response.status_code == 400
            assert "UUID" in response.json()["detail"]


@pytest.mark.asyncio
async def test_citation_artifacts_listed_and_downloadable(
    events, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    app = _research_app(events)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        await _start_and_wait(ac, events, TID)

        # Both citation artifacts are listed by their relative names.
        listing = await ac.get("/api/files", params={"thread_id": TID})
        assert listing.status_code == 200
        names = {f["name"] for f in listing.json()["files"]}
        assert CITATION_REPORT_FILENAME in names
        assert CITATION_PARTITIONS_FILENAME in names

        # The report artifact downloads and is a valid, complete report.
        report_dl = await ac.get(
            "/api/download",
            params={"thread_id": TID, "path": CITATION_REPORT_FILENAME},
        )
        assert report_dl.status_code == 200
        report = json.loads(report_dl.content)
        assert report["schema_version"] == "1.0.0"
        assert set(report["partitions"]) == {
            "rule/offline",
            "semantic/mock",
            "semantic/real",
        }

        # The partitions artifact downloads with one row per partition.
        rows_dl = await ac.get(
            "/api/download",
            params={"thread_id": TID, "path": CITATION_PARTITIONS_FILENAME},
        )
        assert rows_dl.status_code == 200
        rows = [json.loads(line) for line in rows_dl.text.splitlines() if line]
        assert [row["partition_id"] for row in rows] == [
            "rule/offline",
            "semantic/mock",
            "semantic/real",
        ]
        assert all(row["fingerprint"] for row in rows)

        # Artifacts are thread-scoped: the foreign thread lists none.
        other = await ac.get("/api/files", params={"thread_id": TID_OTHER})
        other_names = {f["name"] for f in other.json()["files"]}
        assert CITATION_REPORT_FILENAME not in other_names
        assert CITATION_PARTITIONS_FILENAME not in other_names


@pytest.mark.asyncio
async def test_tutorial_profile_has_no_citation_results(events, tmp_path, monkeypatch):
    """The tutorial profile is untouched: no citation events, no citation API."""
    from app.agent.runtime import MockTutorialRuntime
    from app.providers.contracts import ProviderBundle
    from app.providers.mock import (
        MockCatalogProvider,
        MockKnowledgeRetriever,
        MockWebProvider,
    )

    monkeypatch.chdir(tmp_path)
    bundle = ProviderBundle(
        web=MockWebProvider(),
        catalog=MockCatalogProvider(),
        knowledge=MockKnowledgeRetriever(),
        web_mode="mock",
        catalog_mode="mock",
        knowledge_mode="mock",
    )
    runtime = MockTutorialRuntime(bundle, events)
    app = create_app(
        settings=Phase2Settings(),
        bundle=bundle,
        runtime=runtime,
        events=events,
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        emitted = await _start_and_wait(ac, events, TID_TUTORIAL)
        assert not ({e.type for e in emitted} & CITATION_TYPES)

        response = await ac.get("/api/citations", params={"thread_id": TID_TUTORIAL})
        assert response.status_code == 404
