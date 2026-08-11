"""P4.5-2 deterministic source-locator adapter contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.showcase.contracts import (  # noqa: E402
    SourceKind,
    validate_live_source_result,
)
from app.showcase.locator_adapters import (  # noqa: E402
    normalize_knowledge_chunk,
    normalize_mysql_row,
    normalize_tavily_hit,
    normalize_uploaded_span,
)
from app.showcase.locators import (  # noqa: E402
    LocatorError,
    missing_resolution,
    stale_resolution,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "phase4_5"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_deterministic_fixtures_round_trip_to_valid_live_contracts():
    web = fixture("web.json")
    mysql = fixture("mysql.json")
    knowledge = fixture("knowledge.json")
    upload = fixture("uploaded_file.json")

    records = [
        normalize_tavily_hit(web),
        normalize_mysql_row(mysql),
        normalize_knowledge_chunk(knowledge),
        normalize_uploaded_span(upload),
    ]
    assert [record.source_kind for record in records] == [
        SourceKind.WEB,
        SourceKind.MYSQL,
        SourceKind.KNOWLEDGE,
        SourceKind.UPLOADED_FILE,
    ]
    for record in records:
        validate_live_source_result(record.as_live_source_result())


def test_stable_ids_ignore_metadata_but_change_with_identity():
    hit = fixture("web.json")
    first = normalize_tavily_hit(hit)
    second = normalize_tavily_hit(
        {**hit, "title": "changed", "captured_at": "2027-01-01T00:00:00Z"}
    )
    assert first.source_id == second.source_id
    assert first.source_id.startswith("src-web-")
    assert (
        first.source_id
        != normalize_tavily_hit({**hit, "url": "https://example.com/other"}).source_id
    )


@pytest.mark.parametrize(
    "url",
    ["javascript:alert(1)", "https://u:p@example.com/x", "https://example.com/a\n/b"],
)
def test_web_locator_rejects_unsafe_url(url):
    with pytest.raises(LocatorError):
        normalize_tavily_hit({**fixture("web.json"), "url": url})


def test_web_url_canonicalization_and_safe_link():
    record = normalize_tavily_hit(fixture("web.json"))
    assert record.locator.canonical_url == "https://example.com/docs?a=0&a=1&b=2"
    assert record.safe_display_link == record.locator.canonical_url
    assert "#section" not in record.locator.canonical_url


def test_mysql_query_fingerprint_is_whitespace_stable_and_secret_free():
    payload = fixture("mysql.json")
    first = normalize_mysql_row(payload)
    second = normalize_mysql_row(
        {**payload, "query": " select  id,name  from products where id=7 "}
    )
    assert first.source_id == second.source_id
    assert "SELECT" not in first.as_contract()["value"]
    assert "password" not in first.as_contract()["value"].lower()
    assert first.safe_display_link is None


def test_mysql_rejects_cross_database_and_unsafe_query():
    payload = fixture("mysql.json")
    with pytest.raises(LocatorError):
        normalize_mysql_row({**payload, "query": "SELECT * FROM other.products"})
    with pytest.raises(LocatorError):
        normalize_mysql_row({**payload, "query": "DELETE FROM products"})


def test_knowledge_locator_has_no_clickable_or_secret_link():
    record = normalize_knowledge_chunk(fixture("knowledge.json"))
    assert record.locator.collection_id == "deepsearch-fixture-v1"
    assert record.safe_display_link is None
    with pytest.raises(LocatorError):
        normalize_knowledge_chunk(
            {
                **fixture("knowledge.json"),
                "collection_id": "https://user:secret@example.com",
            }
        )


def test_uploaded_locator_is_thread_scoped_and_relative_link_only():
    payload = fixture("uploaded_file.json")
    record = normalize_uploaded_span(payload)
    assert record.locator.artifact_name == "report.pdf"
    assert (
        record.safe_display_link
        == "/api/threads/aaaaaaaa-0000-4000-8000-000000000001/uploads/report.pdf"
    )
    other = normalize_uploaded_span(
        {**payload, "thread_id": "bbbbbbbb-0000-4000-8000-000000000002"}
    )
    assert record.source_id != other.source_id
    with pytest.raises(LocatorError):
        normalize_uploaded_span({**payload, "artifact_name": "../secret.txt"})
    with pytest.raises(LocatorError):
        normalize_uploaded_span({**payload, "thread_id": "not-a-uuid"})


def test_missing_and_stale_sources_are_explicit_and_stale_cannot_emit_live_result():
    missing = missing_resolution(SourceKind.WEB, "provider unavailable")
    assert missing.locator is None
    assert missing.limitation.code == "missing-source"
    current = normalize_tavily_hit(fixture("web.json"))
    stale = stale_resolution(current, "version changed")
    assert stale.locator is not None
    assert stale.locator.source_id == current.source_id
    assert stale.limitation.code == "stale-source"
    with pytest.raises(LocatorError):
        stale.locator.as_live_source_result()


def test_errors_and_limitations_redact_paths_secrets_and_payloads():
    with pytest.raises(LocatorError) as exc:
        normalize_tavily_hit(
            {
                "url": "https://user:supersecret@example.com/a",
                "title": "x",
                "content": "/Users/wxhu/private/file",
            }
        )
    message = str(exc.value)
    assert "supersecret" not in message
    assert "/Users/wxhu/private" not in message


@pytest.mark.parametrize("field", ["captured_at", "version"])
def test_adapter_fails_closed_when_required_source_metadata_is_missing(field):
    payload = fixture("web.json")
    del payload[field]
    with pytest.raises(LocatorError, match=field):
        normalize_tavily_hit(payload)
