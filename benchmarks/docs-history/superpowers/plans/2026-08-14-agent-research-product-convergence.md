# Agent Research Product Convergence Implementation Plan

> **For agentic workers:** Execute this plan package-by-package inline in the current Codex session. Do not dispatch subagents. Steps use checkbox (`- [ ]`) syntax for tracking. Do not run real LLM, Tavily, MySQL, external data, deployment, release, or publication without separate explicit authorization.

**Goal:** Make `agent-research` the only user-facing product and deliver a capability-graded OpenAI-compatible multi-source research workflow through the existing FastAPI, WebSocket, React, Markdown, PDF, and citation surfaces.

**Architecture:** Preserve HTTP paths, thread workspaces, task lifecycle, WebSocket transport, cancellation, and download safety. Replace the offline research runtime with a `ResearchApplication` composed of capability checks, an OpenAI-compatible model adapter, DeepAgents orchestration, source adapters, evidence normalization, and atomic delivery. Keep `tutorial` and `showcase` only as explicit internal regression adapters until the final removal gate.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, DeepAgents, LangChain OpenAI, LangGraph, Tavily, MySQL Connector, SQLGlot, Qdrant Local, FastEmbed, ReportLab, React 18, TypeScript, Vite, Vitest, Testing Library, pytest.

## Implementation Status Ledger

This ledger keeps the approved design and the executable plan in the same
document without turning an in-progress package into an accepted release.
`Implemented baseline` means the code and nearest tests exist; `Offline
accepted` means the complete credential-free exit gate, including required
browser QA, is recorded. It does not imply live Provider acceptance.

**Active execution cursor:** S3-6 was authorized and executed. Stage 1-3,
including S3-5 fake/local desktop/mobile browser acceptance, remain complete at
the credential-free offline boundary. S3-6 isolated smokes passed, but the
combined live browser journey failed after repeated tool calls, so S3-6 remains
incomplete and is not part of offline convergence acceptance.

| Package | Status | Implemented baseline | Remaining external boundary |
|---|---|---|---|
| S1-1 to S1-4 | Offline accepted | Settings, capability states, OpenAI-compatible model seam, shared evidence contracts, identity and thread validation | None at offline boundary |
| S1-5 to S1-7 | Offline accepted | Web/upload tools, orchestrator, exact artifact set, atomic delivery, cleanup, and upload-to-WebSocket closure | None at offline boundary |
| S1-8 to S1-10 | Offline accepted | Default application wiring, research event v2 lifecycle, canonical result API, and single-mode React workspace | None at offline boundary |
| S2-1 to S2-3 | Offline accepted | MySQL allowlist/AST policy, row and chunk locators, non-mutating knowledge readiness, explicit limitation semantics, mixed-source tests, source-coverage UI, and browser locator review | None at offline boundary |
| S3-1 | Offline accepted | Structured claims, fail-closed identities, cross-thread rejection, server/browser result validation, and delivery-before-reference checks | None at offline boundary |
| S3-2 | Offline accepted | Canonical `/api/research-results` contract and schema `3.0.0` validation | None at offline boundary |
| S3-3 | Offline accepted | Server/browser identity checks, exact artifact validation, strict terminal-event metadata, result-to-event identity comparison, sanitized JSON/Markdown/PDF generation, upload locator isolation, and public-text safety checks | None at offline boundary |
| S3-4 | Offline accepted | Required capability admission, optional-source degradation, safe failure codes, bounded retry, cancellation races, slow-consumer closure, report cleanup, and exactly-one-terminal-event coverage | None at offline boundary |
| S3-5 | Complete | Production assembly and frontend expose only agent-research; historical adapters are test-only; complete credential-free gate and desktop/mobile browser QA passed | None |
| S3-6 | Executed; combined run blocked | Isolated model, Web, read-only MySQL, and local fixture knowledge smokes passed; bounded evidence recorded | New authorization for a combined success run |
| S3-6R | Offline complete | Validated budgets, bounded Agent/Worker middleware, recursion guard, evidence-addressable tool JSON, and safe exhaustion lifecycle | Newly authorized S3-6 combined success run |

### Stage 2 implementation record

The Stage 2 baseline is accepted at the credential-free offline boundary:

| Area | Implemented baseline | Offline acceptance result |
|---|---|---|
| MySQL | `MYSQL_ALLOWED_TABLES`, SQLGlot table-AST enforcement, bounded read-only results, stable row locators, and explicit policy/truncation/no-evidence limitations | Offline gate and browser row-locator review passed |
| Local knowledge | Non-mutating Qdrant Local readiness, manifest/fingerprint/collection checks, bounded retrieval, stable chunk locators, and no-evidence limitation | Offline gate and browser chunk-locator review passed |
| Cross-source runtime | Optional capability wiring, safe mid-task degradation, and deterministic mixed-source integration coverage | Ready/unavailable/degraded matrix passed offline |
| React workspace | Used/unused/unavailable/degraded/disabled source coverage, empty-claims copy, responsive long-locator rendering, and desktop/mobile viewport QA | None at offline boundary |

The focused implementation checks are recorded in `docs/phase-status.md`; this
table records the accepted offline boundary. The S2 checkboxes below remain
historical package steps; real Provider evidence is still outside this gate.

The ledger is descriptive, not an acceptance record. Update it only after the
nearest package gate has been run and the corresponding current facts have been
reflected in `docs/phase-status.md`.

The task checkboxes below track the stated package work. A checked package step
does not accept its enclosing stage: stage acceptance is read only from the
Stage gates and Final Acceptance section. Older Stage 1/2 checkboxes are kept
as planned-gate items; the ledger above is the authoritative record of their
accepted offline baselines.
Current progress is read from this ledger and `docs/phase-status.md`.

## Global Constraints

- Automated tests use injected fakes and do not require credentials or network.
- Real Provider smoke tests require separate explicit authorization.
- The UI and default health response do not expose Profile, Runtime, fixture, mock, tutorial, or showcase concepts.
- LLM and session upload workspace are required task capabilities.
- Web, MySQL, and knowledge are optional and must degrade with explicit limitations.
- Preserve thread isolation, safe paths, read-only SQL, redaction, event ordering, cancellation, and exactly one terminal event.
- The browser never receives Provider credentials.
- Events, JSON, Markdown, and PDF never contain credentials, absolute paths, raw Provider responses, or exception representations.
- Do not commit, push, release, publish, or deploy as part of this plan.

## File Map

Create:

- `app/research/config.py`: immutable agent-research settings.
- `app/research/capabilities.py`: capability states, snapshots, and admission.
- `app/research/model.py`: OpenAI-compatible model construction and safe error classification.
- `app/research/evidence.py`: shared source, locator, evidence, claim, limitation, and document contracts.
- `app/research/collector.py`: thread-scoped evidence collection and deduplication.
- `app/research/tools.py`: normalized Web/upload/MySQL/knowledge tools.
- `app/research/agent.py`: main Agent and expert worker assembly.
- `app/research/orchestrator.py`: runtime execution and draft extraction.
- `app/research/delivery.py`: validated JSON/Markdown/PDF output.
- `app/research/application.py`: top-level runtime/capability assembly.
- `frontend/src/research/contracts.ts`: health, event v2, result v3, error, and artifact types.
- `frontend/src/research/api.ts`: strict HTTP/WebSocket transport.
- `frontend/src/research/useResearchWorkbench.ts`: single-session state machine.
- `frontend/src/research/ResearchWorkspace.tsx`: current single-file research
  workspace containing capability strip, composer, progress, result/report,
  source/evidence inspection, and diagnostics regions. These regions may be
  extracted into focused components later, but the current implementation and
  tests must treat the workspace as the ownership boundary.

Modify:

- `app/main.py`, `app/api/schemas.py`, `app/api/events.py`, `app/api/tasks.py`, `app/api/server.py`.
- `app/providers/tavily.py`, `app/providers/mysql.py`, `app/tools/files.py`, `app/knowledge/qdrant_local.py`.
- `app/showcase/*` only for compatibility imports after shared evidence moves.
- `frontend/src/App.tsx`, `frontend/src/app.css`, and legacy workbench tests during migration.
- Update canonical status docs with current facts after each gate; never use a
  status update to imply package acceptance before its exit gate passes.

## Stage 1: LLM + Web + Upload

### S1-1 Configuration

**Files:** Create `app/research/config.py`; test `tests/unit/research/test_config.py`.

**Interface:**

```python
@dataclass(frozen=True)
class AgentResearchSettings:
    model_name: str
    model_base_url: str | None
    model_api_key: str | None
    tavily_api_key: str | None
    model_timeout_seconds: float
    provider_timeout_seconds: float
    mysql: MySQLSettings
    knowledge: KnowledgeSettings

@classmethod
def from_env(cls, environ: Mapping[str, str]) -> "AgentResearchSettings": ...
```

Steps:

- [ ] Test defaults, OpenAI-compatible URL/model/key fields, timeout bounds, safe relative knowledge path, MySQL fields, and credential absence without startup failure.
- [ ] Run `PYTHONPATH=. .venv/bin/pytest -q tests/unit/research/test_config.py`; expect import failure.
- [ ] Implement lazy, immutable parsing. Never construct clients or touch network/index.
- [ ] Verify the focused pytest and `.venv/bin/ruff check app/research/config.py tests/unit/research/test_config.py`.

Exit: one settings object supports all product capabilities without requiring credentials.

### S1-2 Capability registry and admission

**Files:** Create `app/research/capabilities.py`; test `tests/unit/research/test_capabilities.py`.

**Interface:**

```python
CapabilityName = Literal["llm", "web", "upload", "mysql", "knowledge"]
CapabilityState = Literal["ready", "unavailable", "degraded", "disabled"]

@dataclass(frozen=True)
class CapabilityStatus:
    name: CapabilityName
    status: CapabilityState
    required: bool
    label: str
    message: str
    safe_details: Mapping[str, str]

class CapabilityRegistry:
    def snapshot(self) -> CapabilitySnapshot: ...
    def mark_degraded(self, name: CapabilityName, message: str) -> None: ...
```

Steps:

- [ ] Test all states, required failures, optional limitations, stable Chinese messages, and redaction of secret/path-shaped errors.
- [ ] Confirm the focused test fails before implementation.
- [ ] Implement configuration/local checks only; `/health` must not call LLM/Tavily/SQL/embedding.
- [ ] Verify focused pytest and ruff.

Exit: one Provider-neutral capability snapshot drives health and task admission.

### S1-3 OpenAI-compatible model adapter

**Files:** Create `app/research/model.py`; test `tests/unit/research/test_model.py`.

**Interface:**

```python
@dataclass(frozen=True)
class ModelDescriptor:
    provider: Literal["openai-compatible"]
    model: str
    base_url_configured: bool

def build_agent_model(settings: AgentResearchSettings) -> tuple[Any, ModelDescriptor]: ...
def classify_model_error(exc: Exception) -> ModelUnavailable: ...
```

Steps:

- [ ] Patch `ChatOpenAI` in tests and verify model/key/base URL/timeout, no network construction, and safe auth/timeout/rate-limit/unavailable classification.
- [ ] Confirm focused test fails.
- [ ] Import the SDK lazily; never include the key in descriptors, events, errors, or reports.
- [ ] Run focused pytest and ruff.

Exit: orchestration depends on a small model seam, not SDK configuration.

### S1-4 Shared evidence domain

**Files:** Create `app/research/evidence.py`, `app/research/collector.py`; adapt `app/showcase/contracts.py`, `app/showcase/research.py`, `app/showcase/locators.py`; tests `tests/unit/research/test_evidence.py`, `test_collector.py` plus existing Phase 4.5 locator/contract regressions.

**Interface:**

```python
@dataclass(frozen=True)
class ResearchLocator:
    kind: Literal["url", "row", "chunk", "span"]
    value: str

@dataclass(frozen=True)
class ResearchSource: ...
@dataclass(frozen=True)
class ResearchEvidence: ...
@dataclass(frozen=True)
class ResearchClaim: ...
@dataclass(frozen=True)
class ResearchLimitation: ...
@dataclass(frozen=True)
class ResearchDocument: ...

class EvidenceCollector:
    def add_source(self, source: ResearchSource) -> ResearchSource: ...
    def add_evidence(self, source: ResearchSource, quote: str) -> ResearchEvidence: ...
    def add_limitation(self, limitation: ResearchLimitation) -> None: ...
    def build_document(self, query: str, answer: str,
                       claims: Sequence[ResearchClaim]) -> ResearchDocument: ...
```

Steps:

- [ ] Test all four source kinds, stable IDs, duplicate handling, quote bounds/control characters, redaction, upload thread ownership, invalid locators/claim references, no-evidence limitation, and schema `3.0.0`.
- [ ] Confirm new tests fail.
- [ ] Move reusable behavior once; keep showcase wrappers/import aliases so accepted tests still pass.
- [ ] Run new tests and `tests/unit/phase4_5/test_showcase_contracts.py`, `test_source_locators.py`, `test_showcase_research.py`.

Exit: new product code owns a Provider-neutral evidence seam.

### S1-5 Web and upload tools

**Files:** Create `app/research/tools.py`; modify `app/providers/tavily.py`, `app/tools/files.py`; test `tests/unit/research/test_tools.py` and affected Phase 2 adapter/file tests.

Steps:

- [ ] Test bounded Web results, URL source identity, upload span identity, missing Web limitation, Provider failure degradation, untrusted retrieved text, version 2 events, and no raw SDK output.
- [ ] Confirm focused test fails.
- [ ] Add Tavily timeout/result/quote bounds and a thread-safe upload span reader; preserve legacy helpers.
- [ ] Run focused and Phase 2 regressions.

Exit: the Agent can collect safe Web and uploaded-file evidence.

### S1-6 DeepAgents orchestrator

**Files:** Create `app/research/agent.py`, `app/research/orchestrator.py`; test `tests/unit/research/test_agent.py`, `test_orchestrator.py`.

**Interface:**

```python
def create_research_agent(model: Any, tools: ResearchToolSet) -> Any: ...

class ResearchOrchestrator:
    async def run(self, request: RuntimeRequest) -> RuntimeResult: ...
```

Steps:

- [ ] Patch `create_deep_agent`; assert main Agent, conditional Web worker, main-level upload reader, and no model-owned report writers.
- [ ] Test fake graph streaming for planning, collection, evidence, synthesis, cancellation, model failure, optional Web degradation, and no terminal event from orchestrator.
- [ ] Confirm tests fail.
- [ ] Implement security prompt: retrieved content is untrusted data, claims need evidence, no invented sources, and delivery is application-owned.
- [ ] Run focused tests.

Exit: a fake OpenAI-compatible model completes an LLM + Web + upload run offline.

### S1-7 Atomic delivery

**Files:** Create `app/research/delivery.py`; test `tests/unit/research/test_delivery.py`.

**Interface:**

```python
RESEARCH_CITATIONS_FILENAME = "research-citations.json"
RESEARCH_MARKDOWN_FILENAME = "research-report.md"
RESEARCH_PDF_FILENAME = "research-report.pdf"

class ResearchDelivery:
    def deliver(self, request: RuntimeRequest,
                document: ResearchDocument) -> tuple[str, ...]: ...
```

Steps:

- [ ] Test schema `3.0.0`, identical IDs in JSON/Markdown/PDF, limitations, atomic staging, cleanup on failure, and safe artifact events.
- [ ] Confirm tests fail.
- [ ] Generate all formats from the validated document; the model never chooses filenames or writes files.
- [ ] Run focused pytest.

Exit: one document produces the complete artifact set or no partial publication.

### S1-8 Default application and API

**Files:** Create `app/research/application.py`; modify `app/main.py`, `app/api/schemas.py`, `app/api/server.py`, `app/api/tasks.py`; tests `tests/integration/research/test_api_capabilities.py`, `test_stage1_runtime.py` plus API/WebSocket compatibility regressions.

**Interface:**

```python
@dataclass(frozen=True)
class ResearchApplication:
    runtime: TutorialRuntime
    events: InMemoryEventBus
    capabilities: CapabilityRegistry

def build_research_application(environ: Mapping[str, str]) -> ResearchApplication: ...
```

Steps:

- [ ] Test health with only five capabilities and no Profile/Runtime fields; missing LLM `503` before `task_started`; optional Web `202`; duplicate `409`; existing upload/cancel/files/download/WebSocket paths; explicit internal adapter factories.
- [ ] Confirm tests fail.
- [ ] Make `create_app()` assemble ResearchApplication by default and place admission before registry entry.
- [ ] Run focused and Phase 2/4.5 API regressions.

Exit: default backend is capability-graded agent-research while internal adapters remain testable.

### S1-9 Event version 2

**Files:** Modify `app/api/events.py`, `app/api/tasks.py`; create `tests/unit/research/test_events.py`.

**Interface:**

```python
ResearchEventType = Literal[
  "task_started", "research_planning", "research_step_started",
  "research_step_completed", "source_collected", "evidence_validated",
  "answer_draft_ready", "report_created", "task_completed",
  "task_failed", "task_cancelled"
]
class ResearchEvent(BaseModel):
    version: Literal[2]
    sequence: int
    thread_id: str
    type: ResearchEventType
    message: str
    data: dict[str, JsonValue]
    timestamp: datetime
```

Steps:

- [ ] Test JSON-only payloads, monotonic sequences, v1 internal compatibility, v2 product events, slow consumers, cancellation, and exactly one terminal event.
- [ ] Confirm tests fail.
- [ ] Extend the existing bus; do not create a second event bus. Product emits v2, adapters may emit v1 during migration.
- [ ] Run new and Phase 2 event/task tests.

Exit: transport remains live-only and safe while product events become research-semantic.

### S1-10 Frontend contracts, state, and workspace

**Files:** Create the frontend `research/*` files listed in File Map; modify `frontend/src/App.tsx`, `frontend/src/app.css`, and App tests.

Steps:

- [ ] Add strict TypeScript parsers for capabilities, v2 events, v3 documents, structured task errors, safe locators, and server-returned artifact paths. Reject secrets, absolute paths, invalid IDs, unknown versions, and invalid references.
- [ ] Add `useResearchWorkbench` with one session UUID/WebSocket, capability loading, multi-file uploads, required/optional Start rules, stage mapping, terminal guard, structured errors, cancellation, late-response isolation, result fetch, Markdown preview, and artifact downloads.
- [ ] Add component tests for Chinese-first controls, no legacy mode text, five capability rows, composer, progress, answer, claim-evidence rail, source inspection, limitations, reports, diagnostics, keyboard focus, and mobile order.
- [ ] Confirm each focused test fails before implementation.
- [ ] Implement full-width operational bands, neutral evidence-oriented palette, stable dimensions, visible focus, responsive wrapping, and reduced motion. Keep diagnostics collapsed.
- [ ] Run `pnpm --dir frontend test -- --run`, `pnpm --dir frontend lint`, and `pnpm --dir frontend build`.

Exit: first screen is a usable single-mode research workspace.

### Stage 1 Gate

- [ ] Run all `tests/unit/research`, Stage 1 integration tests, affected Phase 2 API/WebSocket/task tests, and Phase 4.5 compatibility tests.
- [ ] Run frontend tests, lint, and build.
- [ ] Run `.venv/bin/ruff check app/research app/api app/providers app/tools tests/unit/research tests/integration/research` and `git diff --check`.
- [ ] Browser QA with fake Providers only unless live authorization exists; check desktop and mobile viewports for overlap, blank results, unsafe links, and English-only primary controls.

Rollback: switch default assembly back to the explicit internal adapter while retaining the shared evidence module.

## Stage 2: MySQL + Qdrant Local/FastEmbed

### S2-1 Read-only MySQL source

**Files:** modify `app/research/capabilities.py`, `app/research/tools.py`, `app/research/agent.py`, `app/providers/mysql.py`; create `tests/unit/research/test_mysql_source.py`; extend `tests/integration/research/test_stage2_sources.py`.

Steps:

- [ ] Test absent configuration, fake connector readiness, table allowlisting, read-only SQL, cross-database rejection, limits, timeout classification, stable row locators, truncation limitation, and optional continuation.
- [ ] Confirm tests fail.
- [ ] Reuse `validate_readonly_query`; readiness must not query on `/health`.
- [ ] Map rows into normalized sources/evidence and run focused tests plus SQL policy/MySQL regressions.

Exit: MySQL can contribute safe row evidence or an explicit optional limitation.

### S2-2 Local knowledge source

**Files:** modify `app/research/capabilities.py`, `app/research/tools.py`, `app/research/agent.py`, `app/knowledge/qdrant_local.py`; create `tests/unit/research/test_knowledge_source.py`; extend Stage 2 integration tests.

Steps:

- [ ] Test missing index/collection, fingerprint mismatch, embedding failure, ready index, min score, Top-K, no evidence, and complete `collection:document:chunk` locator.
- [ ] Confirm tests fail.
- [ ] Add non-mutating availability checks; never create an empty index from health.
- [ ] Reuse Qdrant Local + FastEmbed and preserve title/version/section metadata. Run focused and knowledge regressions.

Exit: local knowledge contributes real chunk evidence without becoming required.

### S2-3 Source coverage UI

**Files:** modify `frontend/src/research/ResearchWorkspace.tsx` and its focused
tests. Component extraction is optional; it must preserve source-coverage
semantics and the existing research transport contracts.

Steps:

- [ ] Test MySQL row and knowledge chunk locators, ready/unavailable/degraded combinations, zero-source states, counts, truncation/no-evidence, and mobile long-locator wrapping.
- [ ] Confirm tests fail.
- [ ] Implement used/unused/unavailable/degraded distinctions in user vocabulary.
- [ ] Run all frontend research tests, lint, and build.

### Stage 2 Gate and rollback

- [ ] Run Stage 1 gate plus Stage 2 source, SQL, MySQL, knowledge, and frontend surfaces.
- [ ] Run `git diff --check`.
- [ ] Roll back by disabling MySQL and knowledge in capability assembly; Stage 1 remains operational.

## Stage 3: Complete Citations, Reports, Failure Semantics, Legacy Exit

### S3-1 Structured claims

**Files:** modify `app/research/agent.py`, `orchestrator.py`, `evidence.py`; create `tests/unit/research/test_structured_claims.py`.

**Interface:**

```python
class ClaimDraft(BaseModel):
    statement: str
    evidence_ids: list[str]

class ResearchDraft(BaseModel):
    answer: str
    claims: list[ClaimDraft]
```

Steps:

- [x] Test valid/duplicate/unknown evidence IDs, empty statements, unsupported claims, malformed output, injection-shaped retrieved data, and fallback when answer text exists.
- [x] Confirm tests fail; implement fail-closed validation. The model can reference existing IDs but cannot create source/evidence identities.
- [x] Run focused tests.

Verified baseline: mixed supported/unsupported claims are preserved, duplicate
evidence IDs are deduplicated, unsupported claims receive an
`unsupported-claim` limitation, and unknown evidence IDs fail before delivery
without publishing any report artifact. The focused research regression is the
evidence boundary for this package and is included in accepted Stage 3 offline scope.

### S3-2 Canonical results endpoint

**Files:** modify `app/api/schemas.py`, `app/api/server.py`, `frontend/src/research/api.ts`, `useResearchWorkbench.ts`; create/extend result delivery tests.

Add:

```text
GET /api/research-results?thread_id=<uuid>
```

Steps:

- [x] Test success, missing result `404`, invalid UUID `400`, thread mismatch, corrupted result rejection, and no partial response.
- [x] Confirm tests fail.
- [x] Implement schema `3.0.0`; keep `/api/live-citations` as an internal compatibility alias.
- [x] Run backend and frontend focused contract tests.

Verified baseline: `/api/research-results` is the product result contract,
validates schema `3.0.0`, fails closed for missing, malformed, corrupted, or
cross-thread documents, and does not publish partial result data. This package
is included in the accepted Stage 3 offline boundary.

### S3-3 JSON/React/Markdown/PDF parity and security

**Files:** modify `app/research/delivery.py`, `frontend/src/research/api.ts`,
`frontend/src/research/useResearchWorkbench.ts`, and
`frontend/src/research/ResearchWorkspace.tsx`; create or extend focused
delivery, result, hook, and workspace tests. The current React implementation
keeps result and report rendering in `ResearchWorkspace.tsx`; future
component extraction is optional and must not change the transport contract.

Steps:

- [x] For one run, assert the same source locator/evidence ID in API JSON, event completion metadata, React, Markdown, and PDF.
- [x] Inject token-shaped text, absolute paths, raw Provider fragments, HTML/script, oversized quotes, and invalid links; assert rejection or redaction.
- [x] Confirm tests fail; derive every output from ResearchDocument and validate before publication.
- [x] Run focused backend/frontend tests.

Accepted offline implementation: server and browser result validation now
recomputes source/evidence/claim identities, enforces locator-kind and thread
ownership, verifies quote hashes, and requires the exact artifact set. The two
terminal WebSocket events carry a strictly validated document identity summary;
the frontend recomputes the retrieved result identity and refuses publication
when it differs from terminal metadata. JSON, Markdown, and PDF are derived
from a sanitized public document and include the same source, evidence,
locator, answer, and claim content. The focused backend/frontend regressions,
static checks, and `git diff --check` are green. S3-3 is included in the
accepted Stage 3 offline boundary; S3-5 legacy exit, the consolidated offline
gate, and fake/local browser QA are complete. S3-4
is recorded below as the verified lifecycle
boundary rather than an open S3-3 dependency.

### S3-4 Failure matrix (offline accepted)

**Files:** modify `model.py`, `orchestrator.py`, `capabilities.py`, `tasks.py`; create `tests/integration/research/test_failure_matrix.py`, `tests/e2e/research/test_research_closure.py`.

Cover:

```text
missing/auth/timeout/rate-limit LLM
Web/MySQL/knowledge pre-task and mid-task failure
all optional sources unavailable
upload read failure
cancellation during model/tool
delivery failure
slow WebSocket consumer
```

Steps:

- [x] Assert admission, continuation/failure, limitation, artifact, safe-message, cleanup, and exactly one terminal event for every row.
- [x] Confirm tests fail.
- [x] Implement at most one retry for transient rate-limit/unavailable errors; never retry auth, validation, SQL policy, or cancellation.
- [x] Run failure matrix and task/event regressions.

Verified baseline: the model stream classifies authentication, timeout,
rate-limit, unavailable, invalid-response, and unknown failures without raw
Provider text; only rate-limit/unavailable is retried once. Required model and
workspace admission fail before task creation, optional sources continue with
limitations, upload/delivery failures use fixed safe codes, and failed or
cancelled runs remove stale and partial research artifacts. Slow consumers
close with `1013`, the frontend strictly accepts the approved failure codes,
and `TaskRegistry` owns exactly one terminal event. S3-5 legacy exit, the
consolidated offline gate, and fake/local browser QA are complete; Stage 3 is
accepted at the offline boundary.

### S3-5 Remove legacy product branches

**Files:** modify `app/main.py`, `app/settings.py`, `frontend/src/App.tsx`; remove obsolete `frontend/src/workbench/*` only after all imports migrate; update tests/docs after acceptance.

Steps:

- [x] Run a legacy-exit guard and targeted search; production assembly and
  frontend source contain no user-facing Profile/Runtime branch.
- [x] Delete obsolete `frontend/src/workbench/*` modules after replacement
  workspace tests pass.
- [x] Keep tutorial/showcase construction only in explicit internal test
  factories under `tests/support/`.
- [x] Run the complete credential-free offline gate:
```bash
PYTHONPATH=. .venv/bin/pytest -q
.venv/bin/ruff check .
pnpm --dir frontend test -- --run
pnpm --dir frontend lint
pnpm --dir frontend build
git diff --check
```

  The repository backend gate, Ruff, frontend tests, ESLint, TypeScript build,
  Vite production build, and diff check pass. The local pnpm wrapper rejects
  ignored esbuild install scripts before invoking frontend commands, so the
  equivalent checked-in `node_modules/.bin` commands are the recorded frontend
  execution path until dependency policy is resolved.
- [x] Run fake/local desktop and mobile browser QA through the credential-free
  schema 3.0 research harness. Verify the Chinese-first workspace, five
  capabilities, upload, WebSocket progress, mixed-source evidence, locators,
  report links, terminal identity, and no horizontal overflow.
  The deterministic run passed at desktop 1440x900 and mobile 375x812. It used
  Web, MySQL, local-knowledge, and uploaded-file sources; exposed stable
  URL/row/chunk/span locators; matched the terminal event to schema `3.0.0`;
  delivered the exact JSON/Markdown/PDF set; and had no horizontal overflow.
- [x] Update `docs/phase-status.md`, `docs/roadmap.md`, and active phase docs
  with current facts only.

Exit: default product has one mode and no legacy frontend branch; the complete
offline gate and fake/local desktop/mobile browser QA are recorded.

### S3-6 Separately authorized live acceptance

This package was run under explicit authorization. Any repeat live run requires
new authorization.

- [x] Minimal OpenAI-compatible model smoke with safe metadata only.
- [x] Bounded Tavily query and locator validation.
- [x] Authorized non-production read-only MySQL query.
- [x] Local knowledge query and chunk locator parity. One existing fixture was
  used because the formal six-document bodies/index were absent; this is not
  formal-corpus acceptance or a retrieval-quality claim.
- [ ] Combined run with only explicitly authorized Providers.
- [ ] Successful desktop/mobile browser acceptance. The failed state was checked
  at 1440x900 and 375x812 with no horizontal overflow.
- [x] Record bounded commands/results in one evidence record; do not claim
  quality, accuracy, latency, cost, SLA, or production readiness. See
  [S3-6 live acceptance evidence](../../verification/phase-10-s3-6-live-acceptance.md).

Observed blocker: the four-source run repeatedly invoked tools and ended with
one safe failure event without a canonical result or JSON/Markdown/PDF reports.
The S3-6R offline recovery described below is complete. A new combined attempt
still requires separate authorization and must prove the post-recovery live exit
gate before S3-6 can be accepted.

### S3-6R Bounded live recovery

This recovery package is an offline prerequisite for a newly authorized S3-6
combined run. It preserves the DeepAgents main-agent/expert-worker architecture
and does not call a real model or source during implementation or verification.
The package is complete at the offline boundary; it does not accept S3-6 or
authorize the live rerun.

#### S3-6R-1 Budget configuration

**Files:** modify `app/research/config.py`; extend
`tests/unit/research/test_config.py`.

**Interface:**

```python
@dataclass(frozen=True)
class ResearchBudgetSettings:
    graph_recursion_limit: int = 40
    main_model_call_limit: int = 12
    main_worker_call_limit: int = 4
    upload_call_limit: int = 1
    worker_model_call_limit: int = 4
    worker_tool_call_limit: int = 2

@dataclass(frozen=True)
class AgentResearchSettings:
    ...
    budgets: ResearchBudgetSettings = ResearchBudgetSettings()
```

Steps:

- [x] Add a failing defaults test for all six values and an environment parsing
  test for `RESEARCH_GRAPH_RECURSION_LIMIT`,
  `RESEARCH_MAIN_MODEL_CALL_LIMIT`, `RESEARCH_MAIN_WORKER_CALL_LIMIT`,
  `RESEARCH_UPLOAD_CALL_LIMIT`, `RESEARCH_WORKER_MODEL_CALL_LIMIT`, and
  `RESEARCH_WORKER_TOOL_CALL_LIMIT`.
- [x] Add a parameterized failing test proving non-integer, zero, and negative
  values are rejected before application assembly.
- [x] Run `PYTHONPATH=. .venv/bin/pytest -q tests/unit/research/test_config.py`;
  expect failures because `ResearchBudgetSettings` and `budgets` do not exist.
- [x] Implement immutable positive-integer parsing without constructing a model,
  Provider, or local index.
- [x] Re-run the focused test and
  `.venv/bin/ruff check app/research/config.py tests/unit/research/test_config.py`.

Exit: every research run receives one validated immutable budget contract.

#### S3-6R-2 Agent stop protocol and middleware

**Files:** modify `app/research/agent.py`; extend
`tests/unit/research/test_agent.py`.

**Interface:**

```python
def create_research_agent(
    model: Any,
    tools: ResearchToolSet,
    budgets: ResearchBudgetSettings = ResearchBudgetSettings(),
) -> Any: ...
```

Steps:

- [x] Add failing assembly tests that inspect the arguments passed to
  `create_deep_agent`: the main graph has
  `ModelCallLimitMiddleware(run_limit=12, exit_behavior="error")`, a
  `task` limiter with `run_limit=4`, and a `read_uploaded_file` limiter with
  `run_limit=1`.
- [x] In the same tests, prove each conditional expert worker has its own model
  limiter with `run_limit=4` and all-source tool limiter with `run_limit=2`,
  both using `exit_behavior="error"`.
- [x] Add prompt assertions requiring one bounded source pass, no repeated source
  after evidence or limitation, use of only returned evidence IDs, and exactly
  one final `{"answer": ..., "claims": ...}` JSON object. Assert workers stop
  after at most two source calls.
- [x] Run `PYTHONPATH=. .venv/bin/pytest -q tests/unit/research/test_agent.py`;
  expect missing middleware and prompt-contract failures.
- [x] Assemble LangChain `ModelCallLimitMiddleware` and
  `ToolCallLimitMiddleware` on the main graph and each `SubAgent`; keep
  report generation application-owned.
- [x] Re-run the focused test and
  `.venv/bin/ruff check app/research/agent.py tests/unit/research/test_agent.py`.

Exit: model, delegation, upload, and worker source use are independently bounded
with error behavior, while the Agent remains free to choose the research plan.

#### S3-6R-3 Orchestrator recursion and safe exhaustion

**Files:** modify `app/research/orchestrator.py` and
`app/research/application.py`; extend `tests/unit/research/test_orchestrator.py`
and `tests/unit/research/test_application.py`.

**Interface:**

```python
class ResearchBudgetExceeded(RuntimeError):
    code = "research-budget-exhausted"
    safe_message = "研究步骤已达到安全上限，请缩小问题范围后重试"

class ResearchOrchestrator:
    def __init__(..., budgets: ResearchBudgetSettings = ResearchBudgetSettings()): ...
```

Steps:

- [x] Add a failing graph-configuration test requiring
  `recursion_limit=40` beside the thread ID and a failing test proving only the
  final AI message is parsed as the structured draft.
- [x] Add parameterized failing tests for `ModelCallLimitExceededError`,
  `ToolCallLimitExceededError`, and `GraphRecursionError`; each must emerge as
  `ResearchBudgetExceeded` without raw exception text.
- [x] Add an application assembly test proving the same parsed budget object is
  passed to both `create_research_agent` and `ResearchOrchestrator`.
- [x] Run the two focused test files; expect recursion configuration, final-message,
  exception-conversion, and assembly failures.
- [x] Supply the explicit LangGraph recursion limit, retain only the latest final
  AI draft, convert only the three budget exception families, and preserve all
  existing structured upload, delivery, cancellation, and model failures.
- [x] Re-run focused tests and Ruff on the touched modules and tests.

Exit: cost guards fail closed as a distinct research-budget outcome instead of
being retried or misclassified as a model outage.

#### S3-6R-4 Evidence-addressable tool responses

**Files:** modify `app/research/tools.py`; extend
`tests/unit/research/test_tools.py`.

**Interface:** every evidence-producing tool returns JSON containing records of
this shape:

```json
{
  "evidence": [
    {
      "evidence_id": "ev-live-stable-id",
      "source_kind": "web",
      "title": "source title",
      "quote": "validated quote",
      "locator": {"kind": "url", "value": "https://example.test/source"}
    }
  ]
}
```

Steps:

- [x] Extend the fake Web, MySQL, knowledge, and uploaded-file tests to parse tool
  output as JSON and compare every returned `evidence_id`, quote, and locator
  with the server-side collector.
- [x] Run `PYTHONPATH=. .venv/bin/pytest -q tests/unit/research/test_tools.py`;
  expect JSON parsing or missing-field failures for all four source kinds.
- [x] Add one shared serializer for validated `ResearchEvidence` records; include
  safe source kind/title metadata and never serialize raw SDK rows, responses,
  exceptions, credentials, or filesystem paths.
- [x] Keep discovery/no-evidence/optional-failure responses explicit and safe;
  they do not fabricate evidence IDs.
- [x] Re-run the focused test and Ruff on the touched files.

Exit: the model receives exactly the evidence identities that the collector will
later accept in structured claims.

#### S3-6R-5 Task lifecycle mapping and package gate

**Files:** modify `app/api/tasks.py`; extend
`tests/integration/research/test_failure_matrix.py`; run affected research
regressions.

Steps:

- [x] Add a failing lifecycle test whose runtime raises
  `ResearchBudgetExceeded` after three stale/partial report files exist. Assert
  no retry, exactly one `task_failed`, code `research-budget-exhausted`, the fixed
  Chinese message, zero reports, and no raw exception details.
- [x] Run the focused failure-matrix test; expect the generic
  `research_failed` code/message.
- [x] Add the public code and fixed message to `TaskRegistry` without changing
  the existing transient-model retry policy or terminal-event ownership.
- [x] Run the focused configuration, agent, orchestrator, tools, application,
  structured-claims, and failure-matrix tests.
- [x] Run the affected backend research regression surface, then
  `.venv/bin/ruff check app/research app/api/tasks.py tests/unit/research tests/integration/research`,
  the repository formatting check for touched Python files, and
  `git diff --check`.
- [x] Update `docs/phase-status.md`, the Phase 10 boundary, and this ledger with
  current offline facts only. Do not mark S3-6 accepted and do not run a real
  Provider or combined browser journey without a new explicit authorization.

Exit: the bounded recovery package is proven offline and S3-6 is ready for a
separately authorized combined live acceptance attempt.

## Final Acceptance

The convergence is complete only when:

1. Default health exposes five capability states and no Profile/Runtime.
2. Missing LLM/upload reject before task creation.
3. Optional sources independently degrade with honest limitations.
4. Web, MySQL, knowledge, and upload locators validate.
5. API, WebSocket, React, JSON, Markdown, and PDF share identities.
6. Success, degraded, failed, and cancelled runs each emit one terminal event.
7. Complete offline backend/frontend/static/security gates pass.
8. Product UI has no legacy mode controls.
9. Legacy adapters are isolated and removable.
10. Any real Provider claim has separately authorized evidence.

```text
S1-1 config -> S1-2 capabilities -> S1-3 model -> S1-4 evidence
-> S1-5 tools -> S1-6 orchestrator -> S1-7 delivery -> S1-8 API
-> S1-9 events -> S1-10 frontend -> Stage 1 gate
-> S2-1 MySQL -> S2-2 knowledge -> S2-3 UI -> Stage 2 gate
-> S3-1 claims -> S3-2 endpoint -> S3-3 parity -> S3-4 failures
-> S3-5 cleanup -> offline gate -> authorized S3-6
```
