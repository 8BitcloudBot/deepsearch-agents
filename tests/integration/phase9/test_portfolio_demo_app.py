from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.knowledge.contracts import KnowledgeChunk
from examples.portfolio_demo.app import create_demo_app
from scripts.portfolio_demo import create_formal_knowledge_retriever

THREAD_ID = "aaaaaaaa-0000-4000-8000-000000000901"
OTHER_THREAD_ID = "bbbbbbbb-0000-4000-8000-000000000902"
TERMINAL_TYPES = {"task_completed", "task_cancelled", "task_failed"}


class FormalKnowledgeRetriever:
    def search(self, query: str, *, limit: int = 8, **_kwargs):
        assert "retrieved RAG content" in query
        assert limit == 8
        return (
            KnowledgeChunk(
                collection_id="deepsearch-showcase-v1",
                document_id="owasp-prompt-injection",
                chunk_id="owasp-prompt-injection-0014",
                title="LLM Prompt Injection Prevention Cheat Sheet",
                content=(
                    "RAG poisoning inserts malicious content into retrieval sources; "
                    "retrieved content remains untrusted data."
                ),
                score=0.72,
                version="1.0.0+ce65dcc5b175",
                section_path=(
                    "LLM Prompt Injection Prevention Cheat Sheet > "
                    "Common Attack Types > RAG Poisoning"
                ),
            ),
        )


async def _run_scenario(
    tmp_path, monkeypatch, scenario: str, *, knowledge_retriever=None
):
    monkeypatch.chdir(tmp_path)
    app = create_demo_app(scenario, knowledge_retriever=knowledge_retriever)
    events = app.state.portfolio_demo_events
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload = await client.post(
            "/api/upload",
            data={"thread_id": THREAD_ID},
            files={
                "files": (
                    "showcase-notes.txt",
                    b"Repository-safe portfolio fixture.",
                    "text/plain",
                )
            },
        )
        assert upload.status_code == 200

        async with events.subscribe(THREAD_ID) as subscription:
            start = await client.post(
                "/api/task",
                json={
                    "thread_id": THREAD_ID,
                    "query": (
                        "What defenses help an agent treat retrieved RAG content "
                        "as untrusted data rather than instructions?"
                        if scenario == "formal-knowledge"
                        else "Compare evidence-grounded Agent research approaches."
                    ),
                },
            )
            assert start.status_code == 202
            emitted = []
            while True:
                event = await asyncio.wait_for(subscription.queue.get(), timeout=5)
                emitted.append(event)
                if event.type in TERMINAL_TYPES:
                    break

        citations = await client.get(
            "/api/live-citations", params={"thread_id": THREAD_ID}
        )
        files = await client.get("/api/files", params={"thread_id": THREAD_ID})
        return app, emitted, citations, files


@pytest.mark.asyncio
async def test_success_scenario_delivers_four_sources_and_three_artifacts(
    tmp_path, monkeypatch
):
    _app, emitted, citations, files = await _run_scenario(
        tmp_path, monkeypatch, "success"
    )

    assert citations.status_code == 200
    document = citations.json()["document"]
    assert document["schema_version"] == "2.0.0"
    assert {source["source_kind"] for source in document["sources"]} == {
        "web",
        "mysql",
        "knowledge",
        "uploaded-file",
    }
    assert {source["source_kind"]: source["title"] for source in document["sources"]}[
        "knowledge"
    ] == "Trustworthy research architecture"
    assert len(document["evidence"]) == 4
    assert {
        item["source_kind"]: item["thread_id"] for item in document["evidence"]
    } == {
        "web": None,
        "mysql": None,
        "knowledge": None,
        "uploaded-file": THREAD_ID,
    }
    assert document["limitations"] == []
    assert {item["name"] for item in files.json()["files"]} == {
        "live-citations.json",
        "showcase-report.md",
        "showcase-report.pdf",
    }
    assert [event.type for event in emitted if event.type in TERMINAL_TYPES] == [
        "task_completed"
    ]


@pytest.mark.asyncio
async def test_formal_knowledge_scenario_uses_retriever_and_shared_locator(
    tmp_path, monkeypatch
):
    _app, emitted, citations, files = await _run_scenario(
        tmp_path,
        monkeypatch,
        "formal-knowledge",
        knowledge_retriever=FormalKnowledgeRetriever(),
    )

    assert citations.status_code == 200
    document = citations.json()["document"]
    knowledge_sources = [
        source for source in document["sources"] if source["source_kind"] == "knowledge"
    ]
    knowledge_evidence = [
        item for item in document["evidence"] if item["source_kind"] == "knowledge"
    ]
    assert [source["title"] for source in knowledge_sources] == [
        "LLM Prompt Injection Prevention Cheat Sheet"
    ]
    locator = (
        "deepsearch-showcase-v1:owasp-prompt-injection:owasp-prompt-injection-0014"
    )
    assert [item["locator"]["value"] for item in knowledge_evidence] == [locator]
    assert knowledge_sources[0]["locator"]["value"] == locator
    assert {item["name"] for item in files.json()["files"]} == {
        "live-citations.json",
        "showcase-report.md",
        "showcase-report.pdf",
    }
    assert [event.type for event in emitted if event.type in TERMINAL_TYPES] == [
        "task_completed"
    ]


@pytest.mark.asyncio
async def test_formal_knowledge_scenario_opens_the_real_local_index(
    tmp_path, monkeypatch, request: pytest.FixtureRequest
):
    if os.environ.get("SHOWCASE_FORMAL_KNOWLEDGE_SMOKE") != "1":
        pytest.skip("formal knowledge smoke is not explicitly enabled")

    root = Path(__file__).resolve().parents[3]
    retriever = create_formal_knowledge_retriever(root)
    request.addfinalizer(lambda: retriever._get_client().close())
    _app, _emitted, citations, _files = await _run_scenario(
        tmp_path,
        monkeypatch,
        "formal-knowledge",
        knowledge_retriever=retriever,
    )

    document = citations.json()["document"]
    knowledge_sources = [
        source for source in document["sources"] if source["source_kind"] == "knowledge"
    ]
    knowledge_evidence = [
        item for item in document["evidence"] if item["source_kind"] == "knowledge"
    ]
    assert knowledge_sources
    assert knowledge_evidence
    assert all(
        item["locator"]["value"].startswith("deepsearch-showcase-v1:")
        for item in knowledge_evidence
    )
    assert any(
        source["title"] == "LLM Prompt Injection Prevention Cheat Sheet"
        for source in knowledge_sources
    )


@pytest.mark.asyncio
async def test_degraded_scenario_is_explicit_and_keeps_other_sources(
    tmp_path, monkeypatch
):
    _app, emitted, citations, _files = await _run_scenario(
        tmp_path, monkeypatch, "degraded"
    )

    document = citations.json()["document"]
    assert {source["source_kind"] for source in document["sources"]} == {
        "web",
        "mysql",
        "uploaded-file",
    }
    assert document["limitations"] == [
        {
            "code": "knowledge-unavailable",
            "source_kind": "knowledge",
            "message": "formal knowledge collection is unavailable in this demo",
        }
    ]
    assert [event.type for event in emitted if event.type in TERMINAL_TYPES] == [
        "task_completed"
    ]


@pytest.mark.asyncio
async def test_failure_scenario_is_redacted_and_has_one_terminal_event(
    tmp_path, monkeypatch
):
    _app, emitted, citations, _files = await _run_scenario(
        tmp_path, monkeypatch, "failure"
    )

    serialized = citations.text
    document = citations.json()["document"]
    assert document["sources"] == []
    assert document["evidence"] == []
    assert document["limitations"] == [
        {
            "code": "agent-failed",
            "source_kind": None,
            "message": "showcase agent execution failed",
        }
    ]
    assert "raw-secret" not in serialized
    assert "/Users/portfolio/private" not in serialized
    assert [event.type for event in emitted if event.type in TERMINAL_TYPES] == [
        "task_completed"
    ]


@pytest.mark.asyncio
async def test_demo_artifacts_remain_thread_scoped(tmp_path, monkeypatch):
    app, _emitted, _citations, _files = await _run_scenario(
        tmp_path, monkeypatch, "success"
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        foreign_citations = await client.get(
            "/api/live-citations", params={"thread_id": OTHER_THREAD_ID}
        )
        foreign_files = await client.get(
            "/api/files", params={"thread_id": OTHER_THREAD_ID}
        )

    assert foreign_citations.status_code == 404
    assert foreign_files.json()["files"] == []
