# P4.5-4 Citation-Rich Delivery Implementation Plan

> **For the current Codex session:** Execute this plan inline with focused
> TDD cycles. Do not dispatch implementation work, call Reasonix/DeepSeek,
> commit, push, tag, release, use a real provider, or use the network.

**Goal:** Deliver P4.5-3 live sources, evidence, limitations, and deterministic
paragraph claims through thread-scoped JSON, Markdown, PDF, artifact downloads,
and non-terminal WebSocket progress while preserving the Phase 4 API contract.

**Architecture:** Add one showcase delivery module that transforms an already
validated `ShowcaseRunResult` into a canonical live-citation document and three
safe workspace artifacts. Inject it optionally into `ShowcaseResearchRuntime`;
the existing runtime owns session and collector contexts, while delivery owns
rendering, artifact events, and delivery degradation. Add a separate
`/api/live-citations` route that reads only the persisted document.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, existing ReportLab writer,
Dataclasses, existing `InMemoryEventBus`, pytest, Ruff.

## Global Constraints

- Preserve `GET /api/citations`, Phase 4 fixture/report contracts, tutorial,
  agent-research, API schema fields, WebSocket event types, and default artifact
  names unchanged.
- Live data stays in the `live` execution/evidence partition and never enters
  Phase 4 evaluation artifacts, fixtures, or metrics.
- Read no credential unless the existing showcase config already permits it;
  tests use fakes only and do not call a model, Provider, network, or data source.
- Serialize only validated source locators, redacted bounded answer/evidence/
  limitations, safe display links, and relative artifact names.
- `TaskRegistry` remains the only terminal event owner. Delivery only emits
  `citation_started`, `artifact_created`, and `citation_completed`.
- No React work, P4.5-5 polish, P4.5-6 smoke, commits, tags, pushes, releases,
  worktree changes, or unrelated refactors.

---

## File Map

- Create `app/showcase/delivery.py`: canonical delivery claims/document,
  Markdown renderer, artifact writer, and delivery result type.
- Modify `app/showcase/runtime.py`: optional delivery protocol/callback inside
  the existing session/collector lifecycle.
- Modify `app/main.py`: build and inject showcase delivery only in the showcase
  profile.
- Modify `app/showcase/__init__.py`: export P4.5-4 delivery types.
- Modify `app/tools/reports.py`: optional validated basename parameters while
  preserving both existing no-argument report filenames.
- Modify `app/api/schemas.py`: additive live citation response schema.
- Modify `app/api/server.py`: additive `GET /api/live-citations` endpoint.
- Create `tests/unit/phase4_5/test_showcase_delivery.py`: canonical document,
  renderer, redaction, safe link, and failure contracts.
- Modify `tests/unit/phase2/test_reports.py`: additive filename and path-safety
  regression tests.
- Modify `tests/integration/phase4_5/test_showcase_runtime.py`: delivery event,
  artifacts, and TaskRegistry terminal-event contract.
- Create `tests/integration/phase4_5/test_showcase_delivery_api.py`: live API,
  `/api/files`, `/api/download`, and old citation endpoint compatibility.

### Task 1: Safe Additive Report Filenames

**Files:**

- Modify: `app/tools/reports.py`
- Modify: `tests/unit/phase2/test_reports.py`

**Interfaces:**

- Preserve `generate_markdown_report(content: str) -> str` returning
  `"tutorial-report.md"`.
- Preserve `generate_pdf_report(content: str) -> str` returning
  `"tutorial-report.pdf"`.
- Add keyword-only `filename: str = "tutorial-report.md"` and
  `filename: str = "tutorial-report.pdf"` respectively.
- Both implementations must resolve `filename` through the active session's
  `SessionWorkspace.resolve_output()`, require the exact expected extension,
  and return only `Path.name`.

- [ ] **Step 1: Write failing tests**

```python
def test_markdown_writer_accepts_safe_showcase_basename(workspace_context):
    name = generate_markdown_report("# Showcase", filename="showcase-report.md")
    assert name == "showcase-report.md"
    assert workspace_context.workspace.resolve_output(name).read_text() == "# Showcase"


def test_pdf_writer_rejects_path_and_wrong_extension(workspace_context):
    with pytest.raises(ReportGenerationError):
        generate_pdf_report("content", filename="../escape.pdf")
    with pytest.raises(ReportGenerationError):
        generate_pdf_report("content", filename="showcase-report.md")
```

- [ ] **Step 2: Verify RED**

Run:

```bash
PYTHONPATH=. UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run pytest \
  tests/unit/phase2/test_reports.py -q
```

Expected: the safe showcase filename test fails because the writers do not yet
accept `filename`.

- [ ] **Step 3: Implement minimal safe parameters**

```python
def _report_target(filename: str, expected_extension: str) -> tuple[Path, str]:
    from app.api.context import current_session

    if Path(filename).suffix.lower() != expected_extension:
        raise ReportGenerationError("invalid report filename")
    try:
        target = current_session().workspace.resolve_output(filename)
    except Exception as exc:
        raise ReportGenerationError("invalid report filename") from exc
    return target, target.name


def generate_markdown_report(
    content: str, *, filename: str = "tutorial-report.md"
) -> str:
    target, relative_name = _report_target(filename, ".md")
    _atomic_write_bytes(target, content.encode("utf-8"))
    return relative_name
```

Use the same `_report_target` for PDF before creating its temporary PDF file.
Keep the existing `ReportGenerationError` redaction behavior and default
filenames exactly intact.

- [ ] **Step 4: Verify GREEN**

Run the Task 1 command. Expected: report tests pass, including default report
writer behavior and new showcase basename/path rejection cases.

### Task 2: Canonical Live Citation Delivery

**Files:**

- Create: `app/showcase/delivery.py`
- Create: `tests/unit/phase4_5/test_showcase_delivery.py`

**Interfaces:**

```python
LIVE_CITATION_SCHEMA_VERSION = "1.0.0"
LIVE_CITATION_FILENAME = "live-citations.json"
SHOWCASE_MARKDOWN_FILENAME = "showcase-report.md"
SHOWCASE_PDF_FILENAME = "showcase-report.pdf"

@dataclass(frozen=True)
class DeliveryClaim:
    claim_id: str
    statement: str
    evidence_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, object]: ...

@dataclass(frozen=True)
class LiveCitationDocument:
    thread_id: str
    answer: str
    claims: tuple[DeliveryClaim, ...]
    sources: tuple[dict[str, object], ...]
    evidence: tuple[dict[str, object], ...]
    limitations: tuple[dict[str, object], ...]
    artifacts: tuple[str, ...]

    def as_dict(self) -> dict[str, object]: ...
    def as_json(self) -> str: ...

@dataclass(frozen=True)
class ShowcaseDeliveryResult:
    artifacts: tuple[str, ...]
    limitations: tuple[Limitation, ...] = ()

class ShowcaseCitationDelivery:
    def __init__(self, events: InMemoryEventBus): ...
    def deliver(
        self, request: RuntimeRequest, result: ShowcaseRunResult
    ) -> ShowcaseDeliveryResult: ...

def build_live_citation_document(
    thread_id: str, result: ShowcaseRunResult
) -> LiveCitationDocument: ...

def render_showcase_markdown(document: LiveCitationDocument) -> str: ...

def validate_live_citation_document(
    value: Mapping[str, object], *, expected_thread_id: str
) -> dict[str, object]: ...
```

- [ ] **Step 1: Write failing document and renderer tests**

Build a `ShowcaseRunResult` from the four deterministic P4.5-2 fixtures and
assert:

```python
document = build_live_citation_document(THREAD_ID, result)
assert [claim.claim_id for claim in document.claims] == ["claim-1", "claim-2"]
assert document.claims[0].evidence_ids == tuple(
    evidence.evidence_id for evidence in result.evidence
)
assert json.loads(document.as_json())["artifacts"] == [
    "live-citations.json", "showcase-report.md", "showcase-report.pdf"
]
assert "[claim-1]" in render_showcase_markdown(document)
assert "/Users/" not in document.as_json()
assert "raw-secret" not in render_showcase_markdown(document)
```

Add cases for zero evidence, source limitations, one Web safe link, one upload
relative safe link, and MySQL/knowledge records with no link. Assert blank answer
segments do not create claims and zero evidence yields `evidence_ids == ()`.

- [ ] **Step 2: Verify RED**

Run:

```bash
PYTHONPATH=. UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run pytest \
  tests/unit/phase4_5/test_showcase_delivery.py -q
```

Expected: import failure because `app.showcase.delivery` does not exist.

- [ ] **Step 3: Implement canonical document and Markdown renderer**

```python
def build_live_citation_document(
    thread_id: str, result: ShowcaseRunResult
) -> LiveCitationDocument:
    evidence_ids = tuple(item.evidence_id for item in result.evidence)
    claims = tuple(
        DeliveryClaim(f"claim-{index}", redact(paragraph), evidence_ids)
        for index, paragraph in enumerate(_paragraphs(result.answer), start=1)
    )
    sources = tuple(
        source.as_live_source_result(
            expected_thread_id=thread_id
            if source.source_kind is SourceKind.UPLOADED_FILE
            else None
        )
        for source in result.sources
    )
    return LiveCitationDocument(
        thread_id=thread_id,
        answer=redact(result.answer),
        claims=claims,
        sources=sources,
        evidence=tuple(item.as_dict() for item in result.evidence),
        limitations=tuple(item.as_dict() for item in result.limitations),
        artifacts=(
            LIVE_CITATION_FILENAME,
            SHOWCASE_MARKDOWN_FILENAME,
            SHOWCASE_PDF_FILENAME,
        ),
    )
```

`_paragraphs` splits on one-or-more blank lines, strips each segment, and
returns only non-empty strings. `as_json()` uses `json.dumps(...,
sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"`.
`render_showcase_markdown()` renders the exact ordered sections in the approved
design, uses only `safe_display_link` values from the matching source record,
and never derives a link from a locator value.

- [ ] **Step 4: Write failing artifact/event tests**

Within a `session_context`, call `ShowcaseCitationDelivery.deliver()` and
subscribe to the event bus. Assert all three files exist, JSON round-trips,
Markdown and PDF contain the claim marker, event types are exactly:

```python
[
    "citation_started",
    "artifact_created",
    "artifact_created",
    "artifact_created",
    "citation_completed",
]
```

Assert artifact events list only relative names and expected media types. Patch
the PDF writer to raise a secret/path-bearing exception and assert one
`delivery-failed` limitation, no raw marker, no `artifact_created`, and one
`citation_completed` event with `{"status": "degraded"}`.

- [ ] **Step 5: Implement writing and degradation**

```python
def deliver(self, request: RuntimeRequest, result: ShowcaseRunResult) -> ShowcaseDeliveryResult:
    document = build_live_citation_document(request.context.thread_id, result)
    self._events.emit(request.context.thread_id, "citation_started", "showcase delivery", {
        "claim_count": len(document.claims),
        "evidence_count": len(document.evidence),
    })
    try:
        _write_live_json(request.context.workspace, document.as_json())
        generate_markdown_report(render_showcase_markdown(document), filename=SHOWCASE_MARKDOWN_FILENAME)
        generate_pdf_report(render_showcase_markdown(document), filename=SHOWCASE_PDF_FILENAME)
    except Exception:
        limitation = Limitation("delivery-failed", None, "showcase delivery failed")
        self._events.emit(request.context.thread_id, "citation_completed", "showcase delivery", {"status": "degraded"})
        return ShowcaseDeliveryResult((), (limitation,))
    for name, media_type in _ARTIFACTS:
        self._events.emit(request.context.thread_id, "artifact_created", name, {
            "name": name, "path": name, "media_type": media_type,
        })
    self._events.emit(request.context.thread_id, "citation_completed", "showcase delivery", {"status": "completed"})
    return ShowcaseDeliveryResult(document.artifacts)
```

First generate the Markdown, PDF, and JSON under three safe staged basenames
whose final suffixes are `.md`, `.pdf`, and `.json`; use only
`SessionWorkspace.resolve_output()` and `_atomic_write_bytes()`. Promote the
three completed staged files to their public basenames with `os.replace()` only
after all generation succeeds, then emit artifact events. On a generation
failure before promotion, remove only staged files from that attempt; no public
showcase artifact or `artifact_created` event is produced. Never serialize
exception text.

- [ ] **Step 6: Verify GREEN**

Run the Task 2 command. Expected: document, renderer, artifact, PDF, redaction,
and degraded delivery tests pass without any external call.

### Task 3: Runtime Injection and Showcase Assembly

**Files:**

- Modify: `app/showcase/runtime.py`
- Modify: `app/main.py`
- Modify: `app/showcase/__init__.py`
- Modify: `tests/integration/phase4_5/test_showcase_runtime.py`

**Interfaces:**

```python
class ShowcaseDelivery(Protocol):
    def deliver(
        self, request: RuntimeRequest, result: ShowcaseRunResult
    ) -> ShowcaseDeliveryResult: ...

class ShowcaseResearchRuntime:
    def __init__(
        self,
        events: InMemoryEventBus,
        executor: ShowcaseAgentExecutor | None,
        limitations: tuple[Limitation, ...] = (),
        delivery: ShowcaseDelivery | None = None,
    ) -> None: ...
```

- [ ] **Step 1: Write failing runtime tests**

Use the existing `RecordingExecutor` and a deterministic recording delivery:

```python
runtime = ShowcaseResearchRuntime(events, RecordingExecutor(), delivery=delivery)
result = await runtime.run(request)
assert result.artifacts == (
    "live-citations.json", "showcase-report.md", "showcase-report.pdf"
)
assert delivery.calls == 1
```

Add a delivery that returns `ShowcaseDeliveryResult((), (Limitation(...),))`.
Assert the limitation is present in the returned result, `agent_completed`
still occurs, and running through `TaskRegistry` produces exactly one
`task_completed` terminal event. Keep the existing no-delivery tests unchanged.

- [ ] **Step 2: Verify RED**

Run:

```bash
PYTHONPATH=. UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run pytest \
  tests/integration/phase4_5/test_showcase_runtime.py -q
```

Expected: constructor rejects `delivery` or result artifacts remain empty.

- [ ] **Step 3: Implement runtime injection**

After the executor answer is known but before leaving `session_context` and
`collector_context`, create `base_result = collector.snapshot(answer)`. If
delivery exists, call `delivery.deliver(request, base_result)`, append returned
limitations with `collector.add_limitation()`, then return
`collector.snapshot(answer, delivery_result.artifacts)`. If no delivery exists,
retain `collector.snapshot(answer)`. Do not catch `CancelledError`; unexpected
delivery exceptions become one generic `delivery-failed` limitation and do not
emit a terminal event.

In `build_showcase_runtime()`, create `ShowcaseCitationDelivery(events)` only
for the showcase profile and pass it to `ShowcaseResearchRuntime`. Keep model
missing and model-constructor failure paths delivery-enabled so an honest
degraded JSON/Markdown/PDF result is delivered when workspace writes are
available; no executor or Provider is constructed in those paths.

- [ ] **Step 4: Verify GREEN**

Run the Task 3 command. Expected: all previous P4.5-3 runtime event,
cancellation, source collection, lazy construction, and new delivery tests pass.

### Task 4: Live Citation API and Backend Delivery Closure

**Files:**

- Modify: `app/api/schemas.py`
- Modify: `app/api/server.py`
- Create: `tests/integration/phase4_5/test_showcase_delivery_api.py`

**Interfaces:**

```python
class LiveCitationsResponse(BaseModel):
    thread_id: str
    document: dict[str, Any]

GET /api/live-citations?thread_id=<uuid>
```

- [ ] **Step 1: Write failing API closure tests**

Construct an ASGI app using a showcase runtime with a deterministic executor and
delivery. Open `/ws/{thread_id}` through `TestClient` before submitting the task,
collect through the one terminal event, and assert the non-terminal citation
subsequence is `citation_started`, three `artifact_created`, then
`citation_completed`. Separately submit the task through `AsyncClient`, wait for
the deterministic task to finish, then assert:

```python
response = await client.get("/api/live-citations", params={"thread_id": TID})
assert response.status_code == 200
payload = response.json()
assert payload["thread_id"] == TID
assert payload["document"]["schema_version"] == "1.0.0"
assert payload["document"]["claims"][0]["evidence_ids"]
```

Assert `/api/files` lists all three showcase artifacts, `/api/download` returns
`text/markdown` and `application/pdf` for the reports, missing live citation
document is 404, malformed thread is 400, and another valid thread cannot read
the first thread's document. Add a regression request to `/api/citations` for a
Phase 4 evaluation artifact and assert its existing `{thread_id, report}` body
is unchanged.

- [ ] **Step 2: Verify RED**

Run:

```bash
PYTHONPATH=. UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run pytest \
  tests/integration/phase4_5/test_showcase_delivery_api.py -q
```

Expected: 404 because `/api/live-citations` is not registered.

- [ ] **Step 3: Implement additive schema and route**

```python
@app.get("/api/live-citations")
async def get_live_citations(thread_id: str = Query(...)):
    _validate_uuid(thread_id)
    workspace = SessionWorkspace.for_thread(
        thread_id=thread_id, base_upload="updated", base_output="output"
    )
    try:
        path = workspace.resolve_output("live-citations.json")
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="no live citation results for this thread")
    except Exception:
        raise HTTPException(status_code=400, detail="invalid live citation results")
    if document.get("thread_id") != thread_id:
        raise HTTPException(status_code=404, detail="no live citation results for this thread")
    return LiveCitationsResponse(thread_id=thread_id, document=document)
```

Use `validate_live_citation_document()` before returning the response. It must
require the exact top-level keys, live partition source records, relative
artifact names, and matching thread. Do not alter the old citations route.

- [ ] **Step 4: Verify GREEN**

Run the Task 4 command. Expected: end-to-end task, event, JSON API, list,
download, and Phase 4 endpoint compatibility tests pass with fakes only.

### Task 5: Package Verification and Current-State Documentation

**Files:**

- Modify only after successful package verification: `docs/phase-status.md`,
  `docs/phases/phase-4-5-research-showcase.md`, and `docs/roadmap.md` if their
  package facts must be advanced from the stale P4.5-1/P4.5-2 status.

- [ ] **Step 1: Run affected backend regression surface**

```bash
PYTHONPATH=. UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run pytest \
  tests/unit/phase4_5 tests/integration/phase4_5 \
  tests/unit/phase2/test_reports.py tests/unit/phase2/test_runtime_events.py \
  tests/integration/phase2/test_api_contract.py \
  tests/integration/phase2/test_websocket_flow.py \
  tests/unit/phase3/test_research_profile.py \
  tests/integration/phase3/test_research_runtime.py \
  tests/unit/phase4/test_citation_contracts.py \
  tests/integration/phase4/test_citation_api.py -q
```

Expected: all selected tests pass. Do not run the entire repository suite.

- [ ] **Step 2: Run touched-file static checks**

```bash
UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run ruff check \
  app/showcase app/api app/main.py app/tools/reports.py \
  tests/unit/phase4_5 tests/integration/phase4_5

UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run ruff format --check \
  app/showcase app/api app/main.py app/tools/reports.py \
  tests/unit/phase4_5 tests/integration/phase4_5

git diff --check
```

- [ ] **Step 3: Update only current phase facts**

After all gates pass, update the canonical current-state documents to state
that P4.5-2 and P4.5-3 are complete in the existing worktree and P4.5-4 has
completed its bounded backend delivery package. Do not copy command output or
test totals into long-lived status documents, edit historical plan/spec/evidence
records, or claim P4.5-5/P4.5-6 completion.

- [ ] **Step 4: Scope audit**

Inspect `git status --short` and the P4.5-4 diff. Confirm no API/WebSocket
contract removal, frontend, Phase 4 fixture, real provider invocation,
credential, absolute path, remote Git mutation, commit, push, tag, release, or
unrelated worktree change was introduced.

## Self-Review

- Task 1 establishes the safe writer seam used only by Task 2, retaining both
  default filename contracts.
- Task 2 defines all delivery data and failure semantics before runtime wiring.
- Task 3 introduces delivery only as an optional showcase runtime dependency,
  preserving P4.5-3 tests and cancellation behavior.
- Task 4 exposes persisted live data without touching Phase 4's endpoint.
- Task 5 distinguishes package acceptance from full-suite/CI work and limits
  documentation changes to current facts after verification.
