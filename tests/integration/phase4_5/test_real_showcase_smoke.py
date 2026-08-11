"""Explicit opt-in P4.5-6 live Showcase contract smoke."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

import pytest

from app.api.events import InMemoryEventBus
from app.api.tasks import TaskRegistry
from app.knowledge.contracts import resolve_knowledge_index_path
from app.showcase.config import ShowcaseRuntimeConfig
from app.showcase.contracts import LOCATOR_KINDS_BY_SOURCE_KIND, SourceKind
from app.showcase.delivery import validate_live_citation_document
from app.tools.files import SessionWorkspace

SMOKE_FLAG = "PHASE45_REAL_SHOWCASE_SMOKE"
ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "fixtures" / "phase4_5" / "showcase_request.json"
TERMINAL_TYPES = {"task_completed", "task_cancelled", "task_failed"}
ARTIFACTS = (
    "live-citations.json",
    "showcase-report.md",
    "showcase-report.pdf",
)
LEAK_PATTERN = re.compile(
    rb"(?i)(?:(?<![A-Za-z0-9_])(?:sk|tvly)-[A-Za-z0-9_-]{8,}|"
    rb"api[_-]?key\s*[:=]|password\s*[:=]|"
    rb"token\s*[:=]|/Users/|[A-Za-z]:\\Users\\)"
)


def _tree_state(path: Path | None) -> tuple[tuple[str, str, int, int], ...]:
    if path is None or not path.exists():
        return ()
    state: list[tuple[str, str, int, int]] = []
    for item in sorted(path.rglob("*")):
        stat = item.lstat()
        kind = "symlink" if item.is_symlink() else "dir" if item.is_dir() else "file"
        state.append(
            (
                item.relative_to(path).as_posix(),
                kind,
                stat.st_size,
                stat.st_mtime_ns,
            )
        )
    return tuple(state)


def _configured_index_path(config: ShowcaseRuntimeConfig) -> Path | None:
    if not config.capabilities.check(SourceKind.KNOWLEDGE).enabled:
        return None
    try:
        return resolve_knowledge_index_path(
            config.knowledge_index_path or ".data/knowledge-index",
            runtime_root=ROOT,
        )
    except ValueError:
        return None


def test_leak_pattern_distinguishes_tokens_from_words() -> None:
    for safe_text in (b"task-based evaluation", b"mask-token behavior"):
        assert LEAK_PATTERN.search(safe_text) is None

    assert LEAK_PATTERN.search(b"credential " + b"sk-" + b"a" * 16)
    assert LEAK_PATTERN.search(b"credential " + b"tvly-" + b"a" * 16)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_showcase_contract_smoke(tmp_path: Path) -> None:
    if os.environ.get(SMOKE_FLAG) != "1":
        pytest.skip(f"{SMOKE_FLAG} is not set to '1': no live capability is read")

    if os.environ.get("APP_PROFILE") != "showcase":
        pytest.fail("live Showcase smoke requires APP_PROFILE=showcase")
    if os.environ.get("SHOWCASE_ENABLED") != "1":
        pytest.fail("live Showcase smoke requires SHOWCASE_ENABLED=1")

    config = ShowcaseRuntimeConfig.from_env(os.environ)
    if not config.model_available:
        pytest.fail("live Showcase smoke requires a configured model")
    usable_sources = [
        state.source_kind
        for state in config.capabilities.states
        if state.enabled
        and not any(
            item.source_kind is state.source_kind for item in config.limitations
        )
    ]
    if not usable_sources:
        pytest.fail("live Showcase smoke requires at least one usable source")

    index_path = _configured_index_path(config)
    index_before = _tree_state(index_path)
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    thread_id = fixture["thread_id"]
    events = InMemoryEventBus()

    from app.main import build_showcase_runtime

    runtime = build_showcase_runtime(environ=os.environ, events=events)
    if runtime._executor is None:
        pytest.fail("live Showcase runtime could not assemble an executor")

    uploads = tmp_path / "uploads"
    outputs = tmp_path / "outputs"
    workspace = SessionWorkspace.for_thread(
        thread_id=thread_id,
        base_upload=str(uploads),
        base_output=str(outputs),
    )
    workspace.resolve_upload(fixture["upload"]["name"]).write_text(
        fixture["upload"]["content"], encoding="utf-8"
    )
    registry = TaskRegistry(runtime, events, str(uploads), str(outputs))

    async with events.subscribe(thread_id) as subscription:
        registry.start(fixture["query"], thread_id)
        emitted = []
        while True:
            event = await asyncio.wait_for(subscription.queue.get(), timeout=180)
            emitted.append(event)
            if event.type in TERMINAL_TYPES:
                break

    terminals = [event for event in emitted if event.type in TERMINAL_TYPES]
    assert [event.type for event in terminals] == ["task_completed"]

    document_path = workspace.resolve_output("live-citations.json")
    document = validate_live_citation_document(
        json.loads(document_path.read_text(encoding="utf-8")),
        expected_thread_id=thread_id,
    )
    assert document["schema_version"] == "2.0.0"
    assert document["answer"].strip()
    assert not {"agent-failed", "delivery-failed"} & {
        item["code"] for item in document["limitations"]
    }

    source_ids = {source["source_id"] for source in document["sources"]}
    assert all(item["source_id"] in source_ids for item in document["evidence"])
    for source in document["sources"]:
        kind = SourceKind(source["source_kind"])
        assert source["locator"]["kind"] in LOCATOR_KINDS_BY_SOURCE_KIND[kind]

    expected_limitations = [item.as_dict() for item in runtime._limitations]
    assert all(item in document["limitations"] for item in expected_limitations)

    for name in ARTIFACTS:
        artifact = workspace.resolve_output(name)
        assert artifact.is_file() and artifact.stat().st_size > 0
        assert LEAK_PATTERN.search(artifact.read_bytes()) is None
    assert _tree_state(index_path) == index_before
