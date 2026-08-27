# User-Directed Real-Provider Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `executing-plans` and execute inline in the current Codex session with review checkpoints. Do not dispatch subagents, use another coding model, commit, push, publish, or deploy.

**Goal:** Replace the superseded profile/runtime flow with one real agent-research product in which the user selects sources, a real OpenAI-compatible LLM owns research judgment, the application owns execution truth, and every result surface shares schema 4.0.0.

**Architecture:** Introduce explicit request, plan, source-run, coverage, and result value objects. An application-owned coordinator runs the real planner, selected source experts, evidence-gap review, and synthesizer in a bounded state machine; model output is untrusted and cannot decide whether a selected source ran. FastAPI and WebSocket expose the same source-semantic state, while React renders the selected source set and resulting SourceRun ledger directly.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, asyncio, LangGraph/DeepAgents provider adapters, Tavily, read-only MySQL, Qdrant Local + FastEmbed knowledge adapter, pytest, React 18 + TypeScript, Vitest, Testing Library, Playwright.

## Global Constraints

- The browser exposes only agent-research; do not restore a visible Profile or alternate runtime.
- Web is selected by default when ready; MySQL and local knowledge are explicitly user-selected; successfully uploaded files are automatically included and removable before start.
- No upload renders 会话文件：无参考; unselected sources are not limitations; successful zero-match retrieval is 无相关数据命中.
- LLM-only runs are valid and explicitly state that they contain no externally validated citations.
- Search depth is evidence-gap-driven. Budgets are outer safety guards and may not impose a fixed Web search count.
- The application coordinator guarantees every selected source is attempted or classified unavailable/failed; the model cannot silently skip or duplicate a source.
- Provider and model output is untrusted. Evidence IDs, locators, counts, redaction, and artifact names are application-owned.
- Canonical result schema is exactly 4.0.0; JSON, WebSocket identity summaries, Markdown, and PDF use the same IDs.
- Preserve thread ownership, safe paths, read-only SQL, query/URL/content deduplication, redaction, event ordering, one terminal event, and atomic artifact delivery.
- Delete tutorial, showcase, mock, fixture, deterministic-demo, and complete offline product assembly after the replacement path is accepted. Retain pure domain, security, and Provider-adapter contract tests only.
- Real OpenAI-compatible LLM and live source calls are used only in the separately authorized acceptance matrix; this plan itself makes no Provider calls.
- No Git history, handoff, historical plan, verification evidence, commit, push, release, publication, or deployment is part of this implementation.

## File Map And Ownership

Create:
- app/research/run.py: immutable request, plan, source-run statuses, and state transitions.
- app/research/coverage.py: evidence-question coverage and normalized query/URL/content deduplication.
- app/research/coordinator.py: explicit admit, plan, execute, review, refine, synthesize, validate, deliver state machine.
- app/research/workers.py: real planner, source-expert, gap-review, and synthesis seams.

Modify:
- app/research/evidence.py, claims.py, collector.py, delivery.py: schema 4.0.0, claim filtering, and shared delivery identity.
- app/research/application.py, config.py, capabilities.py: real application assembly and readiness.
- app/api/schemas.py, tasks.py, events.py, server.py: request, events, lifecycle, and routes.
- frontend/src/research/contracts.ts, api.ts, useResearchWorkbench.ts, ResearchWorkspace.tsx, frontend/src/app.css: source controls and schema 4.0.0 UI.
- app/settings.py, app/providers/contracts.py, app/providers/factory.py, app/agent/factory.py, app/agent/runtime.py: remove Profile/tutorial/mock assembly.
- canonical docs only after acceptance: docs/phase-status.md, docs/roadmap.md, docs/phases/phase-10-agent-research-convergence.md.

## Implementation Sequence

The work is delivered in three dependency-ordered product stages after the
shared contracts and coordinator foundation:

1. **Stage 1 — LLM + Web + uploads:** prove real planning, adaptive Web
   research, safe uploaded-file evidence, source-semantic progress, and the
   corresponding React workflow. LLM-only is included here because it is the
   zero-external-source form of the same request contract.
2. **Stage 2 — MySQL and local knowledge:** add both opt-in sources to the
   already working Stage 1 path. Neither source is allowed to delay or redefine
   the Web/upload flow.
3. **Stage 3 — complete citations and reports:** close claim-level citation
   validation and one canonical JSON/Markdown/PDF delivery contract across all
   sources.

Legacy product removal, deterministic package gates, and the authorized real
Provider acceptance matrix occur only after all three stages are integrated.

### Task 1: Request, Plan, SourceRun, And Schema 4.0.0 Domain

Files:
- Create app/research/run.py
- Modify app/research/evidence.py and app/research/collector.py
- Test tests/unit/research/test_run.py, test_evidence.py, test_collector.py

Interfaces:
- Produce frozen ResearchSourceSelection(web=True, mysql=False, knowledge=False).
- Produce ResearchRequest(thread_id, query, sources, uploaded_files), EvidenceQuestion, ResearchPlan, SourceExecutionStatus, SourceRun, and ResearchRunLedger.
- Change ResearchDocument to require research_mode, plan, source_runs and literal schema 4.0.0.

- [ ] Step 1: Write failing tests.

~~~python
def test_source_selection_defaults_to_web_only():
    selection = ResearchSourceSelection()
    assert selection.web is True and not selection.mysql and not selection.knowledge

def test_unselected_source_is_not_a_limitation():
    ledger = ResearchRunLedger.for_request(
        ResearchRequest(THREAD_ID, "问题", ResearchSourceSelection(web=False), ())
    )
    assert ledger.source_run("web").status == "not-selected"
    assert ledger.limitations() == ()

def test_upload_without_file_is_no_reference():
    ledger = ResearchRunLedger.for_request(
        ResearchRequest(THREAD_ID, "问题", ResearchSourceSelection(), ())
    )
    assert ledger.source_runs_for("uploaded-file")[0].status == "no-reference"

def test_plan_cannot_assign_unselected_mysql():
    request = ResearchRequest(THREAD_ID, "问题", ResearchSourceSelection(), ())
    plan = ResearchPlan("问题", (EvidenceQuestion("q1", "数据?", ("mysql",), True),))
    with pytest.raises(ValueError, match="source was not selected"):
        plan.validate_against(request)
~~~

- [ ] Step 2: RED. Run: pytest tests/unit/research/test_run.py tests/unit/research/test_evidence.py tests/unit/research/test_collector.py -q. Expected failure: app.research.run is absent and the document still requires schema 3.0.0.
- [ ] Step 3: Implement frozen dataclasses, UUID/upload-basename validation, a single transition table, and ledger methods mark_planned, mark_running, finish. for_request creates not-selected records for disabled sources and no-reference records for an empty upload set; neither creates limitations. Compute modes llm-only, llm+web, llm+uploads, and llm+selected-sources. Update document serialization and parsing while retaining the three approved artifact names.
- [ ] Step 4: GREEN. Run the same focused pytest command; expected all focused tests pass after old 3.0.0 fixtures are migrated.
- [ ] Step 5: Review checkpoint: no Provider imports, no health inference, no model-owned counts, and no circular import.

### Task 2: HTTP Source Selection And Source-Semantic WebSocket Events

Files:
- Modify app/api/schemas.py, app/api/events.py, app/api/tasks.py, app/api/server.py
- Create tests/unit/research/test_request_api.py
- Modify tests/unit/phase2/test_task_registry.py and tests/integration/research/test_api_capabilities.py

Interfaces:
- TaskStartRequest carries query, thread_id, sources, uploaded_files.
- TaskRegistry.start accepts an immutable ResearchRequest.
- Add events research_plan_created, source_planned, source_started, source_matched, source_no_match, source_unavailable, source_failed, source_completed, coverage_reviewed, answer_draft_ready, report_created and the three terminal events.

- [ ] Step 1: RED tests:

~~~python
def test_task_request_preserves_user_source_selection(client, runtime_spy):
    response = client.post("/api/task", json={
        "thread_id": THREAD_ID, "query": "问题",
        "sources": {"web": False, "mysql": True, "knowledge": False},
        "uploaded_files": ["notes.pdf"],
    })
    assert response.status_code == 200
    assert runtime_spy.request.sources.mysql is True
    assert runtime_spy.request.uploaded_files == ("notes.pdf",)

def test_source_event_is_safe(event_bus):
    event_bus.emit_research(THREAD_ID, "source_failed", "检索失败", {
        "source_kind": "web", "status": "failed", "attempt_count": 1,
    })
    event = event_bus.history(THREAD_ID)[-1]
    assert set(event.data) <= {"source_kind", "status", "attempt_count",
        "query_count", "hit_count", "evidence_count", "cited_evidence_count"}
~~~

- [ ] Step 2: RED. Run: pytest tests/unit/research/test_request_api.py tests/unit/phase2/test_task_registry.py -q. Expected failure: request has no source fields and new event types are absent.
- [ ] Step 3: Add strict Pydantic source selection defaults, convert to ResearchRequest, validate filenames against the thread workspace, pass one request snapshot to the registry, extend event allowlists, and sanitize event data. Keep TaskRegistry the sole terminal-event owner.
- [ ] Step 4: GREEN. Run: pytest tests/unit/research/test_request_api.py tests/unit/phase2/test_task_registry.py tests/integration/research/test_api_capabilities.py -q. Expected all pass.
- [ ] Step 5: Review cross-thread rejection, readiness/run separation, and exactly one terminal event.

### Task 3: Explicit Real-LLM Coordinator

Files:
- Create app/research/coordinator.py and app/research/workers.py
- Modify app/research/application.py, app/research/config.py, app/research/agent.py, and app/api/tasks.py
- Create tests/unit/research/test_coordinator.py
- Modify tests/unit/research/test_agent.py and test_application.py

Interfaces:
- Planner.plan(request) -> ResearchPlan.
- GapReviewer.review(plan, ledger) -> CoverageDecision.
- Synthesizer.synthesize(plan, ledger, evidence) -> Draft.
- ResearchCoordinator.run(request) -> ResearchRuntimeResult.

- [ ] Step 1: RED tests using protocol spies (not product modes): planner once; each selected source exactly once; no worker for unselected sources; selected sources receive a question or general probe; gap review sees coordinator counts; valid evidence survives budget exhaustion.
~~~python
async def test_coordinator_attempts_each_selected_source_once(spies):
    request = ResearchRequest(
        THREAD_ID, "问题", ResearchSourceSelection(web=True, mysql=True), ()
    )
    result = await ResearchCoordinator(**spies).run(request)
    assert spies.web.calls == 1 and spies.mysql.calls == 1
    assert spies.knowledge.calls == 0
    assert [run.status for run in result.document.source_runs] == [
        "matched", "no-match", "no-reference"
    ]
~~~
- [ ] Step 2: RED. Run: pytest tests/unit/research/test_coordinator.py tests/unit/research/test_agent.py tests/unit/research/test_application.py -q. Expected failure: no coordinator/worker protocols exist and current ResearchOrchestrator streams an unbounded top-level graph.
- [ ] Step 3: Implement states admit, plan, execute, review, refine, synthesize, validate, deliver. Validate a plan with one bounded retry; assign each source once per pass; allow Web refinement only for unresolved evidence questions after deduplication; map adapter/model exceptions to classified safe outcomes. Keep the real model factory and DeepAgents expert workers behind workers.py; constructor-injected protocols are test seams and cannot be production mock modes.
- [ ] Step 4: GREEN and regression. Run: pytest tests/unit/research/test_coordinator.py tests/unit/research/test_agent.py tests/unit/research/test_application.py tests/integration/research/test_stage1_runtime.py tests/integration/research/test_stage2_sources.py -q. Expected coordinator tests pass; legacy assertions are migrated in Task 8.
- [ ] Step 5: Review the graph for model-controlled loops, duplicate worker creation, fixed search quotas, or evidence-erasing broad exceptions.

### Task 4: Stage 1 Backend — Real LLM + Web + Uploads

Files:
- Modify app/research/workers.py, app/research/tools.py, app/research/runtime.py, app/tools/files.py, app/providers/factory.py, app/providers/contracts.py, app/providers/tavily.py
- Create app/research/coverage.py and tests/unit/research/test_coverage.py
- Modify tests/unit/research/test_tools.py and tests/integration/research/test_stage2_sources.py

Interfaces:
- `WebWorker.execute(question_set, coverage, collector) -> SourceWorkerResult`.
- `UploadWorker.execute(upload_names, thread_workspace, collector) -> tuple[SourceWorkerResult, ...]`.
- `CoverageLedger.add_query(query)`, `add_url(url)`, and `add_content(text)` deduplicate one run.

- [ ] **Step 1: Write the failing tests.** Cover normalized Web queries, canonical URL duplicates, content-hash duplicates, span evidence for each selected upload, no upload as `no-reference`, and Web refinement only for unresolved evidence questions.

```python
def test_web_and_uploads_share_run_coverage():
    coverage = CoverageLedger()
    assert coverage.add_query("LangChain vs LangGraph")
    assert not coverage.add_query("  langchain   vs langgraph ")
    assert coverage.add_url("https://example.com/?utm_source=x")
    assert not coverage.add_url("https://example.com/")
    assert coverage.add_content("same quote")
    assert not coverage.add_content("same quote")
```

- [ ] **Step 2: Run the RED gate.** From the repository root run `pytest tests/unit/research/test_coverage.py tests/unit/research/test_tools.py tests/integration/research/test_stage2_sources.py -q`. Expected: failure because the shared coverage ledger and worker result contract are not complete.
- [ ] **Step 3: Implement the Web/upload slice.** The real LLM formulates the initial and gap-driven Web queries; the coordinator stops only when required questions are covered or the outer budget is exhausted. Normalize queries and URLs, hash content across Web and uploads, and make the collector own evidence IDs, counts, and safe locators. Read every selected thread-owned upload through the existing safe path adapter; never put absolute paths or raw Provider output in events.
- [ ] **Step 4: Run the GREEN gate.** Run the RED command plus `pytest tests/unit/research/test_coordinator.py tests/integration/research/test_failure_matrix.py -q`. Expected: selected Web/upload sources are attempted once per pass, duplicate queries do not create duplicate evidence, and usable evidence survives budget exhaustion.
- [ ] **Step 5: Stage 1 review checkpoint.** Verify the only external source states exercised are Web and uploaded files, LLM-only remains valid, and `not-selected`/`no-reference` do not enter limitations.

### Task 5: Stage 1 Frontend — Web, Upload, And LLM-Only Workflow

Files:
- Modify frontend/src/research/contracts.ts, api.ts, useResearchWorkbench.ts, ResearchWorkspace.tsx, frontend/src/app.css
- Modify frontend/src/research/api.test.ts, useResearchWorkbench.test.tsx, ResearchWorkspace.test.tsx

Interfaces:
- `startResearch(baseUrl, threadId, query, sources, uploadedFiles)` sends the full request snapshot.
- `ResearchWorkspace` renders readiness separately from `SourceRun` execution state.
- Render `not-selected`, `no-reference`, `planned`, `running`, `matched`, `no-match`, `unavailable`, and `failed` without Profile/tutorial/showcase text.

- [ ] **Step 1: Write the failing tests.** Assert Web is checked by default, MySQL/knowledge are unchecked, successful uploads are automatically included and removable, the empty state is `会话文件：无参考`, and LLM-only/selected-source summaries are correct.

```tsx
it("defaults to web and includes an uploaded file", async () => {
  render(<ResearchWorkspace baseUrl="http://api" />);
  expect(screen.getByLabelText("实时网络")).toBeChecked();
  expect(screen.getByLabelText("结构化数据")).not.toBeChecked();
  expect(screen.getByText("会话文件：无参考")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the RED gate.** From `frontend/`, run `./node_modules/.bin/vitest run src/research/api.test.ts src/research/useResearchWorkbench.test.tsx src/research/ResearchWorkspace.test.tsx`. Expected: failures for schema `4.0.0`, source payloads, upload inclusion, and source-semantic result rendering.
- [ ] **Step 3: Implement the Stage 1 workspace.** Add strict TypeScript contracts, source selection controls, upload add/remove state, plan/source progress, and classified Chinese copy. Keep the capability strip readiness-only; do not infer `no-match` or `no-reference` from health. Use stable responsive dimensions for controls and source rows.
- [ ] **Step 4: Run the GREEN/static gate.** From `frontend/`, run `./node_modules/.bin/vitest run src/research/api.test.ts src/research/useResearchWorkbench.test.tsx src/research/ResearchWorkspace.test.tsx`, `./node_modules/.bin/tsc --noEmit`, and `./node_modules/.bin/eslint src --ext .ts,.tsx`. Expected: all pass without changing dependency policy.
- [ ] **Step 5: Stage 1 browser checkpoint.** Against a contract-only API harness, verify desktop and mobile composition, upload inclusion, Web progress, LLM-only copy, and classified terminal states. Do not call a real Provider in this deterministic checkpoint.

### Task 6: Stage 2 Backend And Frontend — MySQL And Local Knowledge

Files:
- Modify app/research/workers.py, app/research/tools.py, app/providers/mysql.py, app/knowledge/qdrant_local.py, app/tools/knowledge.py, app/research/application.py, frontend/src/research/ResearchWorkspace.tsx, frontend/src/app.css
- Create or modify tests/unit/research/test_mysql_source.py, test_knowledge_source.py, test_application.py, and tests/integration/research/test_stage2_sources.py

Interfaces:
- `MySQLWorker.execute(question_set, read_only_connection, collector) -> SourceWorkerResult`.
- `KnowledgeWorker.execute(question_set, knowledge_retriever, collector) -> SourceWorkerResult`.
- MySQL and knowledge toggles remain false by default and are sent only when the user enables them.

- [ ] **Step 1: Write the failing tests.** Prove one validated read-only MySQL statement with row limits and stable locators; zero rows as `no-match`; missing knowledge index as `unavailable`; below-threshold retrieval as `no-match`; and no calls when either source is unselected.
- [ ] **Step 2: Run the RED gate.** Run `pytest tests/unit/research/test_mysql_source.py tests/unit/research/test_knowledge_source.py tests/unit/research/test_application.py tests/integration/research/test_stage2_sources.py -q`. Expected: failures for opt-in worker creation and distinct source outcomes.
- [ ] **Step 3: Implement opt-in adapters.** The coordinator creates each worker only from the immutable request selection. Preserve SQL parser/allowlist/row-limit checks, safe knowledge locators, content-hash deduplication, and classified Provider/adapter errors. A selected source must finish as `matched`, `no-match`, `unavailable`, or `failed`; it may not silently disappear.
- [ ] **Step 4: Extend the React source controls.** Enable the optional toggles only when readiness is true, preserve the user's explicit choice through a run, and show structured-data/local-knowledge outcomes directly from `document.source_runs`.
- [ ] **Step 5: Run the GREEN gate.** Run the RED command plus `frontend/node_modules/.bin/vitest run frontend/src/research/api.test.ts frontend/src/research/useResearchWorkbench.test.tsx frontend/src/research/ResearchWorkspace.test.tsx` from the repository root. Expected: Stage 1 behavior remains unchanged and selected MySQL/knowledge states are truthful.
- [ ] **Step 6: Stage 2 review checkpoint.** Confirm unselected optional sources are `not-selected`, selected zero-result retrieval is `无相关数据命中`, and capability readiness never rewrites the user's request.

### Task 7: Stage 3 — Claim-Level Citations And JSON/Markdown/PDF Reports

Files:
- Modify app/research/claims.py, app/research/evidence.py, app/research/collector.py, app/research/delivery.py, app/api/server.py, frontend/src/research/api.ts, frontend/src/research/ResearchWorkspace.tsx, frontend/src/app.css
- Create tests/unit/research/test_claim_filtering.py and tests/integration/research/test_research_closure.py
- Modify tests/unit/research/test_delivery.py, frontend/src/research/api.test.ts, frontend/src/research/ResearchWorkspace.test.tsx, and tests/integration/research/test_failure_matrix.py

Interfaces:
- `parse_research_draft(..., known_evidence_ids=...)` filters unknown IDs per claim.
- `ResearchDocument.identity_summary()` includes mode, plan, source-run, claim, and evidence identities.
- Delivery returns exactly `research-citations.json`, `research-report.md`, and `research-report.pdf` atomically.

- [ ] **Step 1: Write the failing tests.** Include a valid claim beside an unknown-ID claim, a claim that loses all evidence, source-run rendering for every terminal status, and JSON/Markdown/PDF identity equality.

```python
def test_unknown_evidence_is_filtered_at_claim_level():
    parsed = parse_research_draft(
        '{"answer":"A","claims":[{"statement":"valid","evidence_ids":["ev-known"]},'
        '{"statement":"bad","evidence_ids":["ev-missing"]}]}',
        known_evidence_ids={"ev-known"},
    )
    assert parsed.claims[0].evidence_ids == ("ev-known",)
    assert parsed.unsupported == ("bad",)
```

- [ ] **Step 2: Run the RED gate.** Run `pytest tests/unit/research/test_claim_filtering.py tests/unit/research/test_delivery.py tests/integration/research/test_failure_matrix.py tests/integration/research/test_research_closure.py -q`. Expected: unknown IDs invalidate the whole draft or delivery identities still omit schema `4.0.0` plan/source-run fields.
- [ ] **Step 3: Implement claim-level validation and delivery.** Keep known evidence and valid claims, mark only fully unsupported declarations, and render `No validated citation.` for those claims. Include research plan, source outcomes, no-reference/no-match/unavailable/failed messages, and the same identity fields in JSON, Markdown, and PDF. Use temporary files plus fsync/rename and approved basenames only.
- [ ] **Step 4: Implement result rendering.** The React result view reads `source_runs`, displays citation counts, and distinguishes unsupported claims from source failures without generic `research_failed` copy.
- [ ] **Step 5: Run the GREEN gate.** Run the RED command. Then, from `frontend/`, run `./node_modules/.bin/vitest run src/research/api.test.ts src/research/useResearchWorkbench.test.tsx src/research/ResearchWorkspace.test.tsx`, `./node_modules/.bin/tsc --noEmit`, `./node_modules/.bin/eslint src --ext .ts,.tsx`, and `./node_modules/.bin/vite build`. Expected: all delivery surfaces share schema `4.0.0` identities.
- [ ] **Step 6: Stage 3 review checkpoint.** Verify invalid model IDs cannot erase valid evidence, no-match is not a limitation by itself, and downloaded reports contain no secrets, absolute paths, raw Provider output, or fabricated citations.

### Task 8: Remove Legacy Product And Complete Simulated Journeys

Files:
- Modify/delete app/settings.py, app/providers/contracts.py, app/providers/factory.py, app/providers/mock.py, app/agent/factory.py, app/agent/subagents.py, app/agent/runtime.py, app/research/runtime.py, app/research/contracts.py, app/research/corpus.py
- Delete app/showcase/, examples/portfolio_demo/, examples/research_demo/, scripts/portfolio_demo.py, scripts/research_demo.py
- Delete or migrate tests/support/legacy_app.py, tests/integration/phase2/test_mock_providers.py, tests/integration/phase2/test_mock_runtime.py, tests/integration/phase4_5/test_showcase_runtime.py, tests/integration/phase4_5/test_showcase_delivery_api.py, tests/integration/phase9/test_portfolio_demo_app.py, tests/unit/research/test_demo.py, and tests whose only purpose is fake/offline complete journeys
- Modify tests/unit/research/test_legacy_exit.py, tests/unit/phase2/test_settings.py, tests/unit/phase2/test_provider_factories.py, README.md, docs/README.md

Interfaces:
- Consumes the real coordinator application and retained pure/security/adapter tests from Tasks 1-7.
- Produces one production factory that assembles only real OpenAI-compatible LLM, Tavily, MySQL, local knowledge, and upload adapters; no mock/offline scenario switch or Profile enum remains.

- [ ] Step 1: RED exit tests:
~~~python
def test_production_factory_has_no_mock_or_profile_runtime(tmp_path):
    assert not hasattr(settings, "VALID_APP_PROFILES")
    app = build_research_application(environ_with_real_provider(), runtime_root=tmp_path)
    assert app.runtime.__class__.__name__ == "ResearchCoordinator"
~~~
Also assert no demo script imports product runtime and no user-facing alternate mode assembly exists.
- [ ] Step 2: RED. Run: pytest tests/unit/research/test_legacy_exit.py tests/unit/phase2/test_settings.py tests/unit/phase2/test_provider_factories.py -q. Expected failure: tutorial/showcase/mock settings and factories are still importable.
- [ ] Step 3: Delete listed product assemblies/routes/configuration. Migrate needed path, SQL, redaction, locator, and adapter tests to real worker boundaries before deleting old fixtures. Remove Profile labels and tutorial/showcase copy from user-facing README and app health payloads. Do not delete pure domain/security/adapter tests solely because they live in an old phase directory.
- [ ] Step 4: GREEN. Run: pytest tests/unit/research/test_legacy_exit.py tests/unit/phase2/test_settings.py tests/unit/phase2/test_provider_factories.py tests/unit/research tests/integration/research -q. Expected no legacy product assembly is importable and retained contracts pass.
- [ ] Step 5: Review with rg -n 'mock|offline|tutorial|showcase|portfolio_demo|research_demo|APP_PROFILE|VALID_APP_PROFILES' app frontend/src README.md docs. Classify every hit as retained test-only/domain vocabulary or remove it; no hit may enable a simulated journey.

### Task 9: Deterministic Gates And Package Review

Files:
- Modify affected tests under tests/unit/research and tests/integration/research
- Do not create verification evidence while implementing; record exact outputs only in the package review/acceptance record.

Interfaces:
- Consumes Tasks 1-8.
- Produces deterministic proof of request/state, deduplication, SQL/path safety, redaction, claim filtering, one terminal event, atomic delivery, frontend parsing/rendering, and Provider-adapter contracts.

- [ ] Step 1: Add nearest-boundary tests for every listed contract without a fake product run.
- [ ] Step 2: Backend gate. Run: pytest tests/unit/research tests/integration/research tests/unit/phase2/test_task_registry.py tests/unit/phase2/test_events.py tests/unit/phase2/test_settings.py -q. Expected all retained deterministic research/API/security tests pass without real Provider calls.
- [ ] Step 3: Frontend gate. From `frontend/`, run `./node_modules/.bin/vitest run`, `./node_modules/.bin/tsc --noEmit`, `./node_modules/.bin/eslint src --ext .ts,.tsx`, and `./node_modules/.bin/vite build`. Expected all pass without invoking package installation or changing dependency policy.
- [ ] Step 4: Backend static gate. From the repository root run `.venv/bin/ruff check app tests` and `.venv/bin/ruff format --check app tests`. Expected both pass and active code has no schema `3.0.0` or legacy product imports.
- [ ] Step 5: Review checkpoint: inspect `git diff --check` and the touched-file diff for unrelated changes; do not commit.

### Task 10: Authorized Real-Provider Acceptance Matrix

Files:
- Create docs/superpowers/acceptance/2026-08-14-real-provider-agent-research.md only after execution
- Modify scripts only if a real acceptance runner is needed and cannot create a product mode
- Modify frontend only for defects found during acceptance

Interfaces:
- Consumes configured OpenAI-compatible LLM, Tavily, read-only MySQL, local knowledge, upload workspace, and schema 4.0.0 API/WebSocket/artifact contracts.
- Produces redacted rows with selected sources, plan questions, source-run outcomes/counts, terminal status, evidence/claim IDs, artifacts, desktop/mobile rendering, and classified failures.

- [ ] Step 1: Verify required environment variables without printing values. Use disposable threads and non-sensitive uploads. No Provider call occurs until this checklist is reviewed and explicitly authorized for the current run.
- [ ] Step 2: Run the matrix in implementation order. Stage 1: real LLM + Web without upload; real LLM + Web with non-sensitive upload; intentional LLM-only with all external sources off. Stage 2: selected read-only MySQL; selected local knowledge; selected mixed sources. Stage 3: real zero-match; classified Provider failure, cancellation, and invalid-result recovery; desktop/mobile completion with JSON, Markdown, and PDF downloads.
- [ ] Step 3: Verify selected sources are attempted/classified, unselected are not-selected, no upload is no-reference, no-match is not failure, invalid IDs do not erase valid claims, exactly one terminal event exists, and artifacts contain approved basenames and matching identities.
- [ ] Step 4: Redact credentials, raw Provider responses, SQL secrets, absolute paths, private data, and unsupported quality/cost/latency claims. Keep a failure row when classification and evidence preservation are correct.
- [ ] Step 5: Human review checkpoint before any canonical status update. This task does not authorize push, release, publication, or deployment.

### Task 11: Update Canonical Status From Verified Results

Files:
- Modify docs/phase-status.md, docs/roadmap.md, docs/phases/phase-10-agent-research-convergence.md, docs/README.md

Interfaces:
- Consumes accepted package checks and the redacted matrix.
- Produces current facts only; do not duplicate command output or invent quality metrics.

- [ ] Step 1: Check canonical links and scan for unfinished markers, schema 3.0.0, and offline product claims.
- [ ] Step 2: RED before edits. Run: rg -n '3\.0\.0|offline-demo|mock product|tutorial profile|showcase profile' docs/README.md docs/phase-status.md docs/roadmap.md docs/phases/phase-10-agent-research-convergence.md. Expected superseded references are found.
- [ ] Step 3: Change Phase 10 status/package table only for packages actually reviewed; link one redacted acceptance record; keep unmeasured quality/cost/latency/SLA/production claims out.
- [ ] Step 4: GREEN. Run the same schema/offline scan again and git diff --check. Expected no forbidden current-document matches and no whitespace errors.
- [ ] Step 5: Review that docs state facts, not implementation intentions, and leave the worktree uncommitted.

## Spec Coverage Review

- User source ownership, Web default, automatic uploads, no-reference, and LLM-only: Tasks 1, 2, 4, and 5.
- Real planning, expert research, gap review, adaptive Web, and application execution truth: Tasks 3 and 4.
- Optional MySQL/knowledge and truthful matched/no-match/unavailable/failed outcomes: Task 6.
- Claim-level invalid-ID filtering and shared JSON/Markdown/PDF identities: Task 7.
- Profile/mock/offline/demo removal while retaining pure/security/adapter tests: Task 8.
- Deterministic contract boundary and real Provider authority: Tasks 9 and 10.
- Current documentation discipline: Task 11.

## Plan Self-Review

- Every package has exact file ownership, consumed/produced interfaces, failing tests, RED commands with expected failures, implementation signatures or concrete behavior, GREEN/regression commands, and review checkpoints.
- No task imposes a fixed Web search count or lets health infer run outcomes.
- No task treats a fake adapter as product acceptance.
- Legacy deletion follows the real replacement path and preserves safety/domain/adapter tests.
- No implementation, Provider call, commit, push, release, publication, or deployment occurs while writing or reviewing this plan.
