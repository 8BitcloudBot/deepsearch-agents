"""P4.5-4 canonical live citation delivery contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agent.runtime import RuntimeRequest
from app.api.context import SessionContext, session_context
from app.api.events import InMemoryEventBus
from app.showcase.locator_adapters import (
    normalize_knowledge_chunk,
    normalize_mysql_row,
    normalize_tavily_hit,
    normalize_uploaded_span,
)
from app.showcase.research import LiveSourceCollector
from app.tools.files import SessionWorkspace

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "phase4_5"
THREAD_ID = "aaaaaaaa-0000-4000-8000-000000000001"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _sources():
    return (
        normalize_tavily_hit(_fixture("web.json")),
        normalize_mysql_row(_fixture("mysql.json")),
        normalize_knowledge_chunk(_fixture("knowledge.json")),
        normalize_uploaded_span(_fixture("uploaded_file.json")),
    )


def _result(answer: str = "First paragraph.\n\nSecond paragraph."):
    collector = LiveSourceCollector(THREAD_ID)
    for source in _sources():
        collector.add(source, quote=source.display_text)
    return collector.snapshot(answer)


def test_builds_deterministic_claims_and_json_artifacts():
    from app.showcase.delivery import build_live_citation_document

    document = build_live_citation_document(THREAD_ID, _result())

    assert [claim.claim_id for claim in document.claims] == ["claim-1", "claim-2"]
    assert document.claims[0].evidence_ids == tuple(
        evidence.evidence_id for evidence in _result().evidence
    )
    payload = json.loads(document.as_json())
    assert payload["schema_version"] == "2.0.0"
    assert payload["artifacts"] == [
        "live-citations.json",
        "showcase-report.md",
        "showcase-report.pdf",
    ]
    assert payload["sources"][0]["safe_display_link"] == _sources()[0].safe_display_link
    assert payload["sources"][3]["safe_display_link"].startswith(
        f"/api/threads/{THREAD_ID}/uploads/"
    )


def test_renders_claims_evidence_sources_and_redacts_sensitive_values():
    from app.showcase.delivery import (
        build_live_citation_document,
        render_showcase_markdown,
    )

    document = build_live_citation_document(
        THREAD_ID,
        _result(
            "Claim with password=hunter2 at /Users/wxhu/private/file.\n\nSecond claim."
        ),
    )
    markdown = render_showcase_markdown(document)

    assert "[claim-1]" in markdown
    assert "Claims and Evidence" in markdown
    assert "Evidence" in markdown
    assert "Sources" in markdown
    assert _sources()[0].safe_display_link in markdown
    assert "/api/threads/" + THREAD_ID + "/uploads/" in markdown
    assert "/Users/wxhu/private" not in document.as_json()
    assert "hunter2" not in markdown


def test_empty_answer_segments_and_missing_evidence_remain_explicit():
    from app.showcase.delivery import (
        build_live_citation_document,
        render_showcase_markdown,
    )

    collector = LiveSourceCollector(THREAD_ID)
    result = collector.snapshot("\n\n  \n\n")
    document = build_live_citation_document(THREAD_ID, result)

    assert document.claims == ()
    assert document.evidence == ()
    assert document.limitations[0]["code"] == "no-evidence"
    assert "Claims and Evidence" in render_showcase_markdown(document)


def test_document_validation_rejects_foreign_or_provider_display_links():
    from app.showcase.delivery import (
        build_live_citation_document,
        validate_live_citation_document,
    )

    payload = build_live_citation_document(THREAD_ID, _result()).as_dict()
    payload["sources"][0]["safe_display_link"] = "https://attacker.invalid"
    with pytest.raises(ValueError, match="display link"):
        validate_live_citation_document(payload, expected_thread_id=THREAD_ID)

    payload = build_live_citation_document(THREAD_ID, _result()).as_dict()
    payload["sources"][1]["safe_display_link"] = "/api/threads/foreign/uploads/a.txt"
    with pytest.raises(ValueError, match="display link"):
        validate_live_citation_document(payload, expected_thread_id=THREAD_ID)


def test_delivery_publishes_all_artifacts_and_non_terminal_events(tmp_path):
    from app.showcase.delivery import ShowcaseCitationDelivery

    ws = SessionWorkspace.for_thread(
        thread_id=THREAD_ID,
        base_upload=str(tmp_path / "updated"),
        base_output=str(tmp_path / "output"),
    )
    context = SessionContext(thread_id=THREAD_ID, workspace=ws)
    request = RuntimeRequest(query="showcase", context=context)
    events = InMemoryEventBus()
    recorded: list[tuple[str, str, dict]] = []
    original_emit = events.emit

    def record(thread_id, event_type, message, data=None):
        recorded.append((event_type, message, data or {}))
        return original_emit(thread_id, event_type, message, data)

    events.emit = record  # type: ignore[method-assign]
    with session_context(context):
        delivery = ShowcaseCitationDelivery(events)
        result = delivery.deliver(request, _result())

    assert result.artifacts == (
        "live-citations.json",
        "showcase-report.md",
        "showcase-report.pdf",
    )
    assert all(ws.resolve_output(name).exists() for name in result.artifacts)
    assert [event[0] for event in recorded] == [
        "citation_started",
        "artifact_created",
        "artifact_created",
        "artifact_created",
        "citation_completed",
    ]
    assert [event[2]["media_type"] for event in recorded[1:4]] == [
        "application/json",
        "text/markdown",
        "application/pdf",
    ]
    assert all(
        event[2].get("path", "").startswith("/") is False for event in recorded[1:4]
    )


def test_delivery_failure_is_degraded_and_does_not_publish_partial_artifacts(
    tmp_path, monkeypatch
):
    from app.showcase.delivery import ShowcaseCitationDelivery

    ws = SessionWorkspace.for_thread(
        thread_id=THREAD_ID,
        base_upload=str(tmp_path / "updated"),
        base_output=str(tmp_path / "output"),
    )
    context = SessionContext(thread_id=THREAD_ID, workspace=ws)
    request = RuntimeRequest(query="showcase", context=context)
    events = InMemoryEventBus()
    recorded: list[tuple[str, dict]] = []
    original_emit = events.emit

    def record(thread_id, event_type, message, data=None):
        recorded.append((event_type, data or {}))
        return original_emit(thread_id, event_type, message, data)

    events.emit = record  # type: ignore[method-assign]

    def fail_pdf(*args, **kwargs):
        raise RuntimeError("raw-secret at /Users/wxhu/private/file")

    monkeypatch.setattr("app.showcase.delivery.generate_pdf_report", fail_pdf)
    with session_context(context):
        result = ShowcaseCitationDelivery(events).deliver(request, _result())

    assert result.artifacts == ()
    assert result.limitations[0].code == "delivery-failed"
    assert "raw-secret" not in result.limitations[0].message
    assert not ws.resolve_output("live-citations.json").exists()
    assert not ws.resolve_output("showcase-report.md").exists()
    assert not ws.resolve_output("showcase-report.pdf").exists()
    assert [event[0] for event in recorded] == [
        "citation_started",
        "citation_completed",
    ]
    assert recorded[-1][1] == {"status": "degraded"}
