"""P4.5-3 live evidence and thread-scoped collector contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agent.runtime import RuntimeResult  # noqa: E402
from app.showcase.contracts import Limitation, SourceKind  # noqa: E402
from app.showcase.locator_adapters import (  # noqa: E402
    normalize_knowledge_chunk,
    normalize_mysql_row,
    normalize_tavily_hit,
    normalize_uploaded_span,
)
from app.showcase.locators import LocatorError, stale_resolution  # noqa: E402
from app.showcase.research import LiveSourceCollector  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "phase4_5"
THREAD_ID = "aaaaaaaa-0000-4000-8000-000000000001"
OTHER_THREAD_ID = "bbbbbbbb-0000-4000-8000-000000000002"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _sources():
    return (
        normalize_tavily_hit(_fixture("web.json")),
        normalize_mysql_row(_fixture("mysql.json")),
        normalize_knowledge_chunk(_fixture("knowledge.json")),
        normalize_uploaded_span(_fixture("uploaded_file.json")),
    )


def test_collector_accepts_all_four_sources_and_round_trips_json():
    collector = LiveSourceCollector(THREAD_ID)

    for source in _sources():
        evidence = collector.add(source, quote=source.display_text)
        assert evidence.evidence_id.startswith("ev-live-")
        assert evidence.source_id == source.source_id

    result = collector.snapshot("Research complete")
    assert tuple(source.source_kind for source in result.sources) == (
        SourceKind.WEB,
        SourceKind.MYSQL,
        SourceKind.KNOWLEDGE,
        SourceKind.UPLOADED_FILE,
    )
    assert len(result.evidence) == 4
    assert result.artifacts == ()
    assert isinstance(result, RuntimeResult)
    assert json.loads(json.dumps([item.as_dict() for item in result.evidence]))


def test_collector_deduplicates_stably_and_preserves_first_seen_order():
    collector = LiveSourceCollector(THREAD_ID)
    web, mysql, *_ = _sources()

    first = collector.add(web, quote="same quote")
    duplicate = collector.add(web, quote="same quote")
    second = collector.add(mysql, quote="second quote")
    result = collector.snapshot("done")

    assert duplicate == first
    assert result.sources == (web, mysql)
    assert result.evidence == (first, second)


def test_evidence_identity_is_stable_and_changes_with_quote():
    source = _sources()[0]
    first = LiveSourceCollector(THREAD_ID).add(source, quote="alpha")
    repeat = LiveSourceCollector(THREAD_ID).add(source, quote="alpha")
    changed = LiveSourceCollector(THREAD_ID).add(source, quote="beta")

    assert first == repeat
    assert first.evidence_id != changed.evidence_id
    assert first.content_sha256 != changed.content_sha256


def test_collector_rejects_stale_and_foreign_thread_sources():
    collector = LiveSourceCollector(THREAD_ID)
    stale = stale_resolution(_sources()[0]).locator
    assert stale is not None
    with pytest.raises(LocatorError, match="stale"):
        collector.add(stale, quote="old")

    foreign = normalize_uploaded_span(
        {**_fixture("uploaded_file.json"), "thread_id": OTHER_THREAD_ID}
    )
    with pytest.raises(LocatorError, match="thread"):
        collector.add(foreign, quote="foreign")
    assert collector.snapshot("done").evidence == ()


def test_collector_rejects_foreign_thread_scope_on_non_upload_source():
    collector = LiveSourceCollector(THREAD_ID)
    foreign_web = normalize_tavily_hit(_fixture("web.json"), thread_id=OTHER_THREAD_ID)

    with pytest.raises(LocatorError, match="thread"):
        collector.add(foreign_web, quote="foreign")


def test_collector_bounds_and_redacts_quote_and_limitation():
    collector = LiveSourceCollector(THREAD_ID)
    source = _sources()[0]
    quote = "password=hunter2 at /Users/wxhu/private/file " + ("x" * 3000)
    evidence = collector.add(source, quote=quote)
    collector.add_limitation(
        Limitation(
            code="source-failed",
            source_kind=SourceKind.WEB,
            message="token=raw-secret at /Users/wxhu/private/file",
        )
    )
    result = collector.snapshot("done")

    assert len(evidence.quote) <= 2048
    assert "hunter2" not in evidence.quote
    assert "/Users/wxhu/private" not in evidence.quote
    assert "raw-secret" not in result.limitations[0].message
    assert "/Users/wxhu/private" not in result.limitations[0].message


def test_collector_rejects_empty_quote():
    collector = LiveSourceCollector(THREAD_ID)
    with pytest.raises(LocatorError, match="quote"):
        collector.add(_sources()[0], quote="   ")
