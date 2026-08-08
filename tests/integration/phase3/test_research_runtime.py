"""Integration: versioned corpus validation and offline research runtime.

Covers the P3-1 data contract (manifest paths under data/phase3/sources,
unique source IDs, SHA-256 verification, path escape, schema, UTF-8) and
the deterministic AgentResearchRuntime event/artifact/report contract.
"""

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from pypdf import PdfReader

from app.agent.runtime import RuntimeRequest
from app.api.context import SessionContext
from app.api.events import InMemoryEventBus
from app.research.contracts import Corpus
from app.research.corpus import load_corpus
from app.research.runtime import AgentResearchRuntime
from app.tools.files import SessionWorkspace

TID = "00000000-0000-4000-8000-000000000301"
UNIQUE_MARKER = "UNIQUE-P3-CONSTRAINT-20260807"

TID_A = "00000000-0000-4000-8000-000000000311"
TID_B = "00000000-0000-4000-8000-000000000312"
MARKER_A = "UNIQUE-THREAD-A-MARKER-20260807"
MARKER_B = "UNIQUE-THREAD-B-MARKER-20260807"

FAKE_API_KEY = "sk-test-1234567890abcdef"
FAKE_AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
FAKE_PASSWORD = "hunter2-passw0rd"
UPLOAD_SECRET = "super-secret-42"
POSIX_ABS_PATH = "/Users/wxhu/Documents/private/credentials.pem"
WIN_ABS_PATH = "C:\\Users\\wxhu\\Documents\\private\\notes.txt"

TERMINAL_TYPES = {"task_completed", "task_cancelled", "task_failed"}

WEB_JSON = json.dumps(
    {
        "title": "Web snapshot",
        "origin": "https://example.org/web",
        "captured_at": "2026-08-07",
        "content": "Web snapshot content.",
    },
    indent=2,
).encode("utf-8")
CATALOG_JSON = json.dumps(
    {
        "title": "Catalog",
        "origin": "internal curated",
        "captured_at": "2026-08-07",
        "content": "| framework | offline |\n| --- | --- |\n| DeepAgents | yes |\n",
    },
    indent=2,
).encode("utf-8")
KNOWLEDGE_MD = b"# Evaluation Notes\n\nKnowledge notes content.\n"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _entry(source_id: str, kind: str, path: str, content: bytes, **extra) -> dict:
    entry = {
        "source_id": source_id,
        "kind": kind,
        "path": path,
        "content_sha256": _sha256(content),
    }
    if kind == "knowledge":
        # Knowledge metadata is manifest-owned; the file is plain Markdown.
        entry.update(
            title=f"Title {source_id}",
            origin="https://example.org/",
            captured_at="2026-08-07",
        )
    else:
        # Web/Catalog metadata is duplicated in the JSON file and must
        # equal the manifest entry exactly.
        record = json.loads(content)
        entry.update(
            title=record["title"],
            origin=record["origin"],
            captured_at=record["captured_at"],
        )
    entry.update(extra)
    return entry


def _write_corpus(tmp_path: Path, manifest: dict, files: dict[str, bytes]) -> Path:
    root = tmp_path / "sources"
    root.mkdir(parents=True, exist_ok=True)
    for rel, data in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    mp = root / "manifest.json"
    mp.write_text(json.dumps(manifest), encoding="utf-8")
    return mp


def _extract_pdf_text(path: Path) -> str:
    """Extract the text ReportLab actually wrote into a PDF report."""
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _valid_manifest() -> dict:
    return {
        "corpus_id": "test-corpus-v1",
        "schema_version": 1,
        "captured_at": "2026-08-07",
        "sources": [
            _entry("web-a-v1", "web_snapshot", "web/a.json", WEB_JSON),
            _entry("catalog-a-v1", "catalog", "catalog/a.json", CATALOG_JSON),
            _entry("knowledge-a-v1", "knowledge", "knowledge/a.md", KNOWLEDGE_MD),
        ],
    }


# ── Corpus loader ─────────────────────────────────────────────────────────────


class TestCorpusLoader:
    def test_loads_curated_versioned_corpus(self):
        corpus = load_corpus()
        assert isinstance(corpus, Corpus)
        assert corpus.corpus_id == "agent-research-corpus-v1"
        assert corpus.schema_version == 1
        assert len(corpus.sources) == 3
        assert {s.kind for s in corpus.sources} == {
            "web_snapshot",
            "catalog",
            "knowledge",
        }
        for source in corpus.sources:
            assert source.content
            assert len(source.content_sha256) == 64
            assert source.title
            assert source.origin
            assert source.captured_at

    def test_loads_manifest_json_sources_and_knowledge_markdown(self, tmp_path):
        mp = _write_corpus(
            tmp_path,
            _valid_manifest(),
            {
                "web/a.json": WEB_JSON,
                "catalog/a.json": CATALOG_JSON,
                "knowledge/a.md": KNOWLEDGE_MD,
            },
        )
        corpus = load_corpus(mp)
        by_kind = {s.kind: s for s in corpus.sources}
        assert by_kind["web_snapshot"].content == "Web snapshot content."
        assert by_kind["catalog"].content.startswith("| framework")
        assert by_kind["knowledge"].content.startswith("# Evaluation Notes")

    def test_duplicate_source_ids_rejected(self, tmp_path):
        files = {"web/a.json": WEB_JSON, "catalog/a.json": CATALOG_JSON}
        manifest = _valid_manifest()
        manifest["sources"] = [
            _entry("dup-v1", "web_snapshot", "web/a.json", WEB_JSON),
            _entry("dup-v1", "catalog", "catalog/a.json", CATALOG_JSON),
        ]
        mp = _write_corpus(tmp_path, manifest, files)
        with pytest.raises(ValueError, match="duplicate"):
            load_corpus(mp)

    @pytest.mark.parametrize(
        "bad_path",
        ["../escape.json", "/etc/passwd.json", "web/../../escape.json"],
    )
    def test_path_escape_rejected(self, tmp_path, bad_path):
        manifest = _valid_manifest()
        manifest["sources"] = [
            _entry("web-a-v1", "web_snapshot", bad_path, WEB_JSON),
            _entry("catalog-a-v1", "catalog", "catalog/a.json", CATALOG_JSON),
            _entry("knowledge-a-v1", "knowledge", "knowledge/a.md", KNOWLEDGE_MD),
        ]
        mp = _write_corpus(
            tmp_path,
            manifest,
            {"catalog/a.json": CATALOG_JSON, "knowledge/a.md": KNOWLEDGE_MD},
        )
        with pytest.raises(ValueError, match="escape"):
            load_corpus(mp)

    def test_hash_mismatch_rejected(self, tmp_path):
        manifest = _valid_manifest()
        manifest["sources"] = [
            _entry("web-a-v1", "web_snapshot", "web/a.json", WEB_JSON),
            _entry("catalog-a-v1", "catalog", "catalog/a.json", CATALOG_JSON),
            _entry("knowledge-a-v1", "knowledge", "knowledge/a.md", KNOWLEDGE_MD),
        ]
        manifest["sources"][2]["content_sha256"] = "0" * 64
        mp = _write_corpus(
            tmp_path,
            manifest,
            {
                "web/a.json": WEB_JSON,
                "catalog/a.json": CATALOG_JSON,
                "knowledge/a.md": KNOWLEDGE_MD,
            },
        )
        with pytest.raises(ValueError, match="mismatch"):
            load_corpus(mp)

    def test_non_utf8_knowledge_rejected(self, tmp_path):
        manifest = _valid_manifest()
        manifest["sources"] = [
            _entry("web-a-v1", "web_snapshot", "web/a.json", WEB_JSON),
            _entry("catalog-a-v1", "catalog", "catalog/a.json", CATALOG_JSON),
            _entry(
                "knowledge-a-v1",
                "knowledge",
                "knowledge/a.md",
                b"\xff\xfe not utf-8",
            ),
        ]
        mp = _write_corpus(
            tmp_path,
            manifest,
            {
                "web/a.json": WEB_JSON,
                "catalog/a.json": CATALOG_JSON,
                "knowledge/a.md": b"\xff\xfe not utf-8",
            },
        )
        with pytest.raises(ValueError, match="UTF-8"):
            load_corpus(mp)

    def test_unknown_manifest_field_rejected(self, tmp_path):
        manifest = _valid_manifest()
        manifest["extra"] = True
        mp = _write_corpus(tmp_path, manifest, {})
        with pytest.raises(ValueError, match="unknown field"):
            load_corpus(mp)

    def test_unknown_source_field_rejected(self, tmp_path):
        manifest = _valid_manifest()
        manifest["sources"][0]["extra"] = True
        mp = _write_corpus(tmp_path, manifest, {"web/a.json": WEB_JSON})
        with pytest.raises(ValueError, match="unknown field"):
            load_corpus(mp)

    @pytest.mark.parametrize(
        ("field", "expected"),
        [
            ("source_id", "source_id"),
            ("title", "title"),
            ("origin", "origin"),
            ("captured_at", "captured_at"),
            ("kind", "kind"),
            ("path", "path"),
            ("content_sha256", "content_sha256"),
        ],
    )
    def test_missing_required_source_field_rejected(self, tmp_path, field, expected):
        manifest = _valid_manifest()
        del manifest["sources"][0][field]
        mp = _write_corpus(tmp_path, manifest, {"web/a.json": WEB_JSON})
        with pytest.raises(ValueError, match=expected):
            load_corpus(mp)

    def test_non_string_kind_rejected(self, tmp_path):
        manifest = _valid_manifest()
        manifest["sources"][0]["kind"] = ["web_snapshot"]
        mp = _write_corpus(tmp_path, manifest, {"web/a.json": WEB_JSON})
        with pytest.raises(ValueError, match="kind"):
            load_corpus(mp)

    def test_non_string_path_rejected(self, tmp_path):
        manifest = _valid_manifest()
        manifest["sources"][0]["path"] = 12345
        mp = _write_corpus(tmp_path, manifest, {"web/a.json": WEB_JSON})
        with pytest.raises(ValueError, match="path"):
            load_corpus(mp)

    def test_non_string_hash_rejected(self, tmp_path):
        manifest = _valid_manifest()
        manifest["sources"][0]["content_sha256"] = ["x"] * 64
        mp = _write_corpus(tmp_path, manifest, {"web/a.json": WEB_JSON})
        with pytest.raises(ValueError, match="content_sha256"):
            load_corpus(mp)

    @pytest.mark.parametrize("field", ["corpus_id", "captured_at", "sources"])
    def test_missing_required_manifest_field_rejected(self, tmp_path, field):
        manifest = _valid_manifest()
        del manifest[field]
        mp = _write_corpus(tmp_path, manifest, {})
        with pytest.raises(ValueError):
            load_corpus(mp)

    def test_unknown_kind_rejected(self, tmp_path):
        manifest = _valid_manifest()
        manifest["sources"] = [
            _entry("web-a-v1", "video", "web/a.json", WEB_JSON),
            _entry("catalog-a-v1", "catalog", "catalog/a.json", CATALOG_JSON),
            _entry("knowledge-a-v1", "knowledge", "knowledge/a.md", KNOWLEDGE_MD),
        ]
        mp = _write_corpus(
            tmp_path,
            manifest,
            {
                "web/a.json": WEB_JSON,
                "catalog/a.json": CATALOG_JSON,
                "knowledge/a.md": KNOWLEDGE_MD,
            },
        )
        with pytest.raises(ValueError, match="kind"):
            load_corpus(mp)

    def test_missing_source_file_rejected(self, tmp_path):
        manifest = _valid_manifest()
        manifest["sources"] = [
            _entry("web-a-v1", "web_snapshot", "web/missing.json", WEB_JSON),
            _entry("catalog-a-v1", "catalog", "catalog/a.json", CATALOG_JSON),
            _entry("knowledge-a-v1", "knowledge", "knowledge/a.md", KNOWLEDGE_MD),
        ]
        mp = _write_corpus(
            tmp_path,
            manifest,
            {"catalog/a.json": CATALOG_JSON, "knowledge/a.md": KNOWLEDGE_MD},
        )
        with pytest.raises(ValueError, match="not found"):
            load_corpus(mp)

    def test_unsupported_schema_version_rejected(self, tmp_path):
        manifest = _valid_manifest()
        manifest["schema_version"] = 2
        mp = _write_corpus(tmp_path, manifest, {})
        with pytest.raises(ValueError, match="schema_version"):
            load_corpus(mp)

    def test_unknown_field_in_json_source_rejected(self, tmp_path):
        bad_json = json.dumps(
            {
                "title": "Bad",
                "origin": "x",
                "captured_at": "2026-08-07",
                "content": "x",
                "extra": 1,
            }
        ).encode("utf-8")
        manifest = _valid_manifest()
        manifest["sources"] = [
            _entry("web-a-v1", "web_snapshot", "web/a.json", bad_json),
            _entry("catalog-a-v1", "catalog", "catalog/a.json", CATALOG_JSON),
            _entry("knowledge-a-v1", "knowledge", "knowledge/a.md", KNOWLEDGE_MD),
        ]
        mp = _write_corpus(
            tmp_path,
            manifest,
            {
                "web/a.json": bad_json,
                "catalog/a.json": CATALOG_JSON,
                "knowledge/a.md": KNOWLEDGE_MD,
            },
        )
        with pytest.raises(ValueError, match="unknown field"):
            load_corpus(mp)


# ── AgentResearchRuntime ──────────────────────────────────────────────────────


@pytest.fixture
def events():
    return InMemoryEventBus()


@pytest.fixture
def workspace(tmp_path: Path):
    return SessionWorkspace.for_thread(
        thread_id=TID,
        base_upload=str(tmp_path / "updated"),
        base_output=str(tmp_path / "output"),
    )


async def _run(runtime, events, workspace, query="Compare agent orchestration."):
    ctx = SessionContext(thread_id=TID, workspace=workspace)
    async with events.subscribe(TID) as sub:
        result = await runtime.run(RuntimeRequest(query, ctx))
        emitted = []
        while not sub.queue.empty():
            emitted.append(sub.queue.get_nowait())
    return result, emitted


class TestAgentResearchRuntime:
    @pytest.mark.asyncio
    async def test_full_flow_events_artifacts_and_report(self, events, workspace):
        runtime = AgentResearchRuntime(events)
        result, emitted = await _run(runtime, events, workspace)

        assert result.artifacts == ("tutorial-report.md", "tutorial-report.pdf")
        assert len(result.answer) > 50

        event_types = {e.type for e in emitted}
        assert "agent_started" in event_types
        assert "agent_completed" in event_types
        assert "tool_started" in event_types
        assert "tool_completed" in event_types
        assert "artifact_created" in event_types
        assert not (
            {"task_started", "task_completed", "task_cancelled", "task_failed"}
            & event_types
        )

        tool_names = {e.data.get("tool_name", "") for e in emitted}
        assert {
            "read_web_snapshot",
            "read_catalog_entry",
            "read_knowledge_notes",
        } <= tool_names, f"missing source tool events: {sorted(tool_names)}"

        md = workspace.resolve_output("tutorial-report.md")
        pdf = workspace.resolve_output("tutorial-report.pdf")
        assert md.exists()
        assert pdf.exists()
        assert pdf.read_bytes().startswith(b"%PDF")

        content = md.read_text(encoding="utf-8")
        assert "agent-research" in content
        assert "agent-research-corpus-v1" in content
        assert "## Source Modes" in content
        assert "offline" in content

    @pytest.mark.asyncio
    async def test_uploaded_constraint_included_in_report(self, events, workspace):
        (workspace.upload_dir / "constraints.md").write_text(
            f"# {UNIQUE_MARKER}\n\nKeep it short.", encoding="utf-8"
        )
        runtime = AgentResearchRuntime(events)
        result, _ = await _run(runtime, events, workspace)
        assert UNIQUE_MARKER in result.answer
        md = workspace.resolve_output("tutorial-report.md")
        assert UNIQUE_MARKER in md.read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_report_contains_no_absolute_paths(self, events, workspace, tmp_path):
        runtime = AgentResearchRuntime(events)
        result, _ = await _run(runtime, events, workspace)
        leaked = {
            str(Path(tmp_path / "updated").resolve()),
            str(Path(tmp_path / "output").resolve()),
        }
        for marker in leaked:
            assert marker not in result.answer, (marker, result.answer)
            assert marker not in result.answer.replace("\\", "/")

    @pytest.mark.asyncio
    async def test_deterministic_reruns(self, events, tmp_path):
        ws_a = SessionWorkspace.for_thread(
            thread_id=TID,
            base_upload=str(tmp_path / "a" / "updated"),
            base_output=str(tmp_path / "a" / "output"),
        )
        ws_b = SessionWorkspace.for_thread(
            thread_id=TID,
            base_upload=str(tmp_path / "b" / "updated"),
            base_output=str(tmp_path / "b" / "output"),
        )
        runtime = AgentResearchRuntime(events)
        await _run(runtime, events, ws_a)
        await _run(runtime, events, ws_b)
        md_a = ws_a.resolve_output("tutorial-report.md").read_bytes()
        md_b = ws_b.resolve_output("tutorial-report.md").read_bytes()
        assert md_a == md_b

    @pytest.mark.asyncio
    async def test_report_redacts_secrets_and_absolute_paths(self, events, workspace):
        query = (
            "Compare providers with key sk-test-1234567890abcdef, "
            "api_key=AKIAIOSFODNN7EXAMPLE and token=hunter2-passw0rd stored at "
            f"{POSIX_ABS_PATH} and {WIN_ABS_PATH}."
        )
        (workspace.upload_dir / "secrets.md").write_text(
            f"password={UPLOAD_SECRET}\n{POSIX_ABS_PATH}\n{WIN_ABS_PATH}\n",
            encoding="utf-8",
        )
        runtime = AgentResearchRuntime(events)
        result, _ = await _run(runtime, events, workspace, query=query)

        md = workspace.resolve_output("tutorial-report.md").read_text(encoding="utf-8")
        pdf_text = _extract_pdf_text(workspace.resolve_output("tutorial-report.pdf"))

        for leaked in (
            FAKE_API_KEY,
            FAKE_AWS_KEY,
            FAKE_PASSWORD,
            UPLOAD_SECRET,
            POSIX_ABS_PATH,
            WIN_ABS_PATH,
        ):
            assert leaked not in result.answer, leaked
            assert leaked not in md, leaked
            assert leaked not in pdf_text, leaked

        # Stable redaction markers in Markdown, answer and PDF-derived text.
        for text in (result.answer, md, pdf_text):
            assert "[REDACTED]" in text

        # Curated versioned sources retain their reviewed content verbatim.
        curated = load_corpus()
        for source in curated.sources:
            assert source.content in md, source.kind
            assert source.content in result.answer, source.kind


@pytest.mark.asyncio
async def test_two_threads_do_not_cross_markers_artifacts_or_events(
    events, tmp_path, monkeypatch
):
    """Two concurrent agent-research tasks: unique uploaded markers,
    artifacts and events stay inside their own thread."""
    from app.api.server import create_app as create_server
    from app.settings import Phase2Settings

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_PROFILE", "agent-research")
    settings = Phase2Settings.from_env()
    runtime = AgentResearchRuntime(events)
    app = create_server(settings=settings, bundle=None, runtime=runtime, events=events)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        for tid, marker in ((TID_A, MARKER_A), (TID_B, MARKER_B)):
            r = await ac.post(
                "/api/upload",
                data={"thread_id": tid},
                files={
                    "files": (
                        "constraints.md",
                        f"# {marker}\n\nKeep it short.".encode(),
                        "text/markdown",
                    )
                },
            )
            assert r.status_code == 200

        async with events.subscribe(TID_A) as sub_a, events.subscribe(TID_B) as sub_b:
            ra = await ac.post(
                "/api/task",
                json={
                    "query": f"Research thread A with {MARKER_A}.",
                    "thread_id": TID_A,
                },
            )
            rb = await ac.post(
                "/api/task",
                json={
                    "query": f"Research thread B with {MARKER_B}.",
                    "thread_id": TID_B,
                },
            )
            assert ra.status_code == 202
            assert rb.status_code == 202

            async def _collect(sub):
                got = []
                while True:
                    evt = await asyncio.wait_for(sub.queue.get(), timeout=10.0)
                    got.append(evt)
                    if evt.type in TERMINAL_TYPES:
                        return got

            evts_a = await _collect(sub_a)
            evts_b = await _collect(sub_b)

        for tid, evts in ((TID_A, evts_a), (TID_B, evts_b)):
            assert all(e.thread_id == tid for e in evts)
            seqs = [e.sequence for e in evts]
            assert seqs == sorted(seqs)
            assert len(set(seqs)) == len(seqs)
            terminals = [e for e in evts if e.type in TERMINAL_TYPES]
            assert len(terminals) == 1
            assert terminals[0].type == "task_completed"
            artifact_names = {e.message for e in evts if e.type == "artifact_created"}
            assert artifact_names == {"tutorial-report.md", "tutorial-report.pdf"}

        for tid, marker, other in (
            (TID_A, MARKER_A, MARKER_B),
            (TID_B, MARKER_B, MARKER_A),
        ):
            r = await ac.get("/api/files", params={"thread_id": tid})
            assert r.status_code == 200
            fnames = {f["name"] for f in r.json()["files"]}
            assert {"tutorial-report.md", "tutorial-report.pdf"} <= fnames
            r = await ac.get(
                "/api/download", params={"thread_id": tid, "path": "tutorial-report.md"}
            )
            assert r.status_code == 200
            assert marker in r.text
            assert other not in r.text
