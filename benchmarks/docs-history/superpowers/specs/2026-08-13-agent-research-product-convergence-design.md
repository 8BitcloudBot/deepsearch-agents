# Agent Research Product Convergence Design

**Date:** 2026-08-13

**Status:** Approved design baseline

**Approved:** 2026-08-14

This specification is the implementation contract for the confirmed Phase 10
design. It defines product semantics, backend and frontend contracts, security
invariants, and migration gates. It does not record package completion or
authorize real Provider calls. Current progress is maintained only in
[phase status](../../phase-status.md), while package order and verification
work are maintained in the
[implementation plan](../plans/2026-08-14-agent-research-product-convergence.md).
The decision rationale and phase boundary are recorded in
[ADR 0005](../../adr/0005-agent-research-product-convergence.md) and the
[Phase 10 document](../../phases/phase-10-agent-research-convergence.md).

## 1. Objective

Reshape Deepsearch into one user-facing product mode: `agent-research`.
The default application must present a real multi-source research workflow
instead of exposing tutorial, fixture, runtime, or profile concepts to users.

The target product flow is:

```text
research question
  -> OpenAI-compatible main agent and expert workers
  -> Tavily Web / uploaded files / read-only MySQL / local knowledge
  -> normalized sources, evidence, claims, and limitations
  -> FastAPI + WebSocket progress
  -> React research workspace
  -> Markdown / PDF / citation JSON
```

This is a gradual convergence. The existing `tutorial` and `showcase`
implementations remain temporarily available as internal test adapters. They
are not user-selectable, do not appear in the default health response, and do
not shape the new product interface. They may be deleted only after the real
`agent-research` path passes the complete acceptance gate.

## 2. Confirmed Decisions

1. The product UI and default API expose only `agent-research`.
2. `tutorial` and `showcase` remain internal regression adapters during the
   migration.
3. The model integration is OpenAI-compatible and uses:
   `MODEL_BASE_URL`, `MODEL_NAME`, and `MODEL_API_KEY`.
4. All four source capabilities are in scope:
   Tavily Web, uploaded files, read-only MySQL, and Qdrant Local + FastEmbed.
5. Startup is capability-graded. One unavailable optional Provider does not
   stop the API process.
6. The LLM and session workspace are required task capabilities.
7. Web, MySQL, and local knowledge are optional task capabilities. Their
   absence produces explicit limitations instead of fabricated evidence.
8. Delivery is staged:
   - Stage 1: LLM + Web + uploads;
   - Stage 2: MySQL + local knowledge;
   - Stage 3: complete citation validation and report parity.
9. Existing HTTP paths, thread isolation, WebSocket transport, cancellation,
   file safety, and download paths are preserved where possible.
10. No UI allows users to choose `tutorial`, `showcase`, `mock`, or fixtures.

## 3. Scope

### 3.1 In Scope

- A real OpenAI-compatible DeepAgents research runtime.
- Main-agent and specialist-worker orchestration.
- Tavily live Web retrieval.
- Multi-file, thread-scoped upload use.
- Read-only MySQL discovery and querying.
- Qdrant Local + FastEmbed knowledge retrieval.
- Capability checks and task admission.
- Provider-neutral source and evidence contracts.
- Research-semantic WebSocket events.
- Claim-to-evidence linkage and explicit limitations.
- Markdown, PDF, and citation JSON generated from one validated document.
- A Chinese-first operational research workspace.
- Internal compatibility adapters for the accepted tutorial/showcase tests.

### 3.2 Out of Scope

- A visible Profile switcher.
- Fixture or mock modes in the product UI.
- Provider credentials entered or stored in the browser.
- Multiple native model SDK integrations in the first version.
- Write-capable SQL.
- General-purpose crawling or enterprise knowledge management.
- Durable task recovery after process restart. That remains a separate
  persistence package.
- Deployment, production credentials, live smoke execution, push, release, or
  publication as part of this design.
- Claims about real-model quality, search accuracy, latency, cost, SLA, or
  production readiness without separately authorized measurements.

## 4. Product Semantics

The application is an evidence-oriented research workspace. Users control a
research question and optional reference files. They do not control or need to
understand internal profiles, runtime implementations, fixtures, or SDK names.

User-visible vocabulary is fixed as follows:

| Internal concept | User-visible term |
|---|---|
| LLM | 研究模型 |
| Tavily Provider | 实时网络检索 |
| upload workspace | 会话文件 |
| MySQL catalog | 结构化数据 |
| Qdrant/FastEmbed | 本地知识库 |
| thread ID | 研究会话编号, shown only in details |
| tool call | 研究步骤 |
| citation document | 结论与证据 |
| artifact | 研究报告 |

The UI must not show `Profile`, `Runtime`, `tutorial`, `showcase`, `mock`,
`fixture`, Provider class names, raw tool names, citation fingerprints, or
evaluation partitions in its primary workflow.

## 5. Runtime Rules

### 5.1 Minimum and Complete Capability Sets

Minimum runnable set:

```text
OpenAI-compatible LLM + session workspace
```

Recommended Stage 1 set:

```text
OpenAI-compatible LLM + Tavily Web + session workspace
```

Complete set:

```text
OpenAI-compatible LLM + Tavily Web + session workspace
  + read-only MySQL + Qdrant Local/FastEmbed
```

### 5.2 Task Admission

- If `llm` is unavailable, reject the task before creating a registry entry.
- If `upload` workspace initialization is unavailable, reject the task before
  creating a registry entry.
- If Web, MySQL, or knowledge is unavailable, accept the task and attach a
  structured limitation.
- An optional Provider may fail during a task. The task continues with the
  remaining capabilities if the main Agent can still synthesize an answer.
- A completed task may have `completed` or `degraded` delivery status.
- A failed model orchestration or failed final delivery produces one
  `task_failed` terminal event.
- `TaskRegistry` remains the sole owner of exactly one terminal task event.

### 5.3 Evidence Honesty

Every final statement is represented as a claim with zero or more evidence
references. The system distinguishes:

- supported claim: one or more validated evidence records;
- unsupported claim: no evidence was found;
- unavailable source: a capability was absent or failed;
- unused source: the source was ready but did not contribute evidence.

Unsupported content must not be rendered with a source badge. Optional source
failure must be visible in both the result document and the reports.

## 6. Backend Architecture

### 6.1 Module Map

```text
app/main.py
  -> ResearchApplication
      -> CapabilityRegistry
      -> ResearchTaskAdmission
      -> ResearchOrchestrator
          -> AgentModelAdapter
          -> ResearchToolSet
              -> WebSearchAdapter
              -> UploadAdapter
              -> MySQLReadOnlyAdapter
              -> KnowledgeRetrieverAdapter
          -> EvidenceCollector
          -> ResearchDelivery
```

The external seam is `ResearchApplication`: the API layer asks it for
capabilities, task admission, and a runtime. Provider construction and
orchestration remain hidden behind that interface.

### 6.2 Configuration

Create immutable `AgentResearchSettings` in `app/research/config.py`. It owns
only `agent-research` configuration and reads credentials lazily for the
capability that consumes them.

Required fields include:

```text
MODEL_BASE_URL
MODEL_NAME
MODEL_API_KEY
TAVILY_API_KEY
MYSQL_HOST
MYSQL_PORT
MYSQL_USER
MYSQL_PASSWORD
MYSQL_DATABASE
KNOWLEDGE_INDEX_PATH
KNOWLEDGE_COLLECTION
KNOWLEDGE_EMBEDDING_MODEL
KNOWLEDGE_MIN_SCORE
RESEARCH_MODEL_TIMEOUT_SECONDS
RESEARCH_PROVIDER_TIMEOUT_SECONDS
```

`APP_PROFILE` is no longer part of normal product configuration. An internal
test factory may accept an explicit adapter name without reading it from the
default application environment.

### 6.3 Capability Registry

`CapabilityRegistry` reports the state of five capabilities:

```text
llm, web, upload, mysql, knowledge
```

Allowed states:

```text
ready, unavailable, degraded, disabled
```

Contract:

```python
@dataclass(frozen=True)
class CapabilityStatus:
    name: CapabilityName
    status: CapabilityState
    required: bool
    label: str
    message: str
    safe_details: Mapping[str, str]
```

Checks are bounded and safe:

- configuration-only checks run during application assembly;
- local upload and knowledge-path checks may access local files;
- external connectivity probes are not performed on every `/health` request;
- Provider request failures may update an in-memory degraded state;
- raw exception text is never returned.

`/health` returns the current registry snapshot. It must remain fast and must
not trigger an LLM completion, Tavily search, SQL query, or embedding request.

### 6.4 OpenAI-Compatible Model Adapter

The model adapter hides `ChatOpenAI` and Provider-specific construction. Its
interface is the model object accepted by `create_deep_agent`, plus safe model
metadata for capability reporting.

Construction rules:

- `MODEL_API_KEY` and `MODEL_NAME` are required;
- `MODEL_BASE_URL` is optional so the official OpenAI endpoint remains valid;
- no credential value appears in `repr`, errors, events, health, or reports;
- request timeout is explicit;
- initialization does not send a completion request;
- runtime failures are classified into authentication, timeout, rate limit,
  unavailable, malformed response, and unknown safe categories.

### 6.5 Research Orchestrator

The orchestrator uses DeepAgents with a main Agent and only the workers whose
capabilities are ready:

```text
web-research worker       -> Tavily search
catalog-research worker   -> read-only MySQL tools
knowledge-research worker -> Qdrant Local retrieval
main Agent                -> uploaded-file reading and final synthesis
```

The main prompt requires:

- a research plan before source use;
- retrieved text treated as untrusted data, never instructions;
- claims grounded in collected evidence;
- explicit disclosure of missing sources and unsupported claims;
- no invented URLs, rows, chunks, versions, or quotes;
- no report-file tool calls by the model; delivery is application-owned.

The model produces a structured answer draft. The application, not the model,
owns final normalization and report generation.

### 6.6 Provider Adapters

Provider adapters convert SDK results into internal source records. They own
timeouts, result limits, error classification, and safe messages.

Web result identity:

```text
source_kind: web
locator: url
version: provider capture timestamp or supplied version
```

Uploaded-file identity:

```text
source_kind: uploaded-file
locator: filename:start-end span
thread_id: required
```

MySQL identity:

```text
source_kind: mysql
locator: database.table:stable-row-reference
```

Knowledge identity:

```text
source_kind: knowledge
locator: collection:document:chunk
```

MySQL retains the existing SQL parser and read-only policy. Knowledge reuses
the existing `KnowledgeRetriever` interface and Qdrant Local implementation.

### 6.7 Evidence Domain

Move the generally useful source, evidence, claim, and limitation concepts out
of the showcase-specific namespace into `app/research/evidence.py`.

```python
SourceKind = Literal["web", "mysql", "knowledge", "uploaded-file"]
LocatorKind = Literal["url", "row", "chunk", "span"]

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
```

The evidence collector validates and deduplicates source identities, creates
stable evidence IDs, redacts unsafe values, preserves thread ownership for
uploads, and rejects invalid locators.

The existing showcase classes become compatibility wrappers or import aliases
during migration. New product code must not import from `app.showcase`.

### 6.8 Delivery

`ResearchDelivery` accepts only a validated `ResearchDocument` and writes:

```text
research-citations.json
research-report.md
research-report.pdf
```

All three artifacts share the same claim, evidence, source, and limitation
identities. Writes are staged and atomically renamed. Partial delivery files
are removed on failure. Reports include:

- query;
- answer;
- claim and evidence sections;
- source inventory;
- unavailable and unused capabilities;
- model name and safe run metadata;
- no credentials, absolute paths, raw Provider responses, or stack traces.

## 7. HTTP And WebSocket Contracts

### 7.1 Health

Target response:

```json
{
  "status": "ok",
  "service": "deepsearch-agent-research",
  "capabilities": {
    "llm": {
      "status": "ready",
      "required": true,
      "label": "研究模型",
      "message": "研究模型已连接",
      "safe_details": {
        "provider": "openai-compatible",
        "model": "configured-model"
      }
    }
  }
}
```

The public response has no Profile or Runtime fields.

### 7.2 Task Start Errors

Required capability failure uses HTTP `503`:

```json
{
  "error": {
    "code": "required_capability_unavailable",
    "message": "研究模型当前不可用，暂时不能开始研究",
    "capability": "llm"
  }
}
```

Other existing status meanings remain:

- `202`: task created;
- `409`: active task already exists for the thread;
- `422`: request validation failed.

### 7.3 Research Events Version 2

Version 2 event types are:

```text
task_started
research_planning
research_step_started
research_step_completed
source_collected
evidence_validated
answer_draft_ready
report_created
task_completed
task_failed
task_cancelled
```

The envelope keeps `sequence`, `thread_id`, `message`, `data`, and `timestamp`.
The event bus accepts version 1 internal-adapter events and version 2 product
events during migration. The product frontend accepts only version 2.

Events are live-only in this package. Replay and persistence are not implied.

### 7.4 Research Document Version 3

`GET /api/live-citations` remains as a compatibility alias during Stages 1
and 2. Stage 3 adds the canonical endpoint:

```text
GET /api/research-results?thread_id=<uuid>
```

Both return `ResearchDocument` schema `3.0.0` during the transition. After
acceptance, the frontend uses only `/api/research-results`; the old endpoint
remains internal until showcase tests are migrated.

## 8. Frontend Design

### 8.1 Information Architecture

The first screen is the operational research workspace, not a landing page.

```text
Application header and new-research action
Capability status strip
Research composer and uploaded-file list
Live research stage band
Research answer
Claim-to-evidence trace
Source inventory and limitations
Report preview and downloads
Collapsed technical diagnostics
```

Desktop uses an unframed two-column result area: answer and claims on the
left, evidence/source inspection on the right. Mobile follows the same order
in one column. Page sections are full-width bands; cards are reserved for
individual sources and evidence records.

### 8.2 Visual Direction

The interface is quiet, utilitarian, and evidence-oriented.

Color tokens:

```text
canvas       #F4F6F8
surface      #FFFFFF
ink          #17202A
muted        #5C6875
border       #C8D0D9
information  #1F5F99
positive     #18794E
warning      #A15C00
danger       #B42318
```

Typography uses the platform UI sans stack for Chinese readability and the
platform monospace stack only for locators and identifiers. Font sizes are
fixed by role and do not scale with viewport width.

The distinctive element is an evidence rail: each claim expands into its
supporting quotations and then into the stable source locator. This visualizes
the product's defining relationship without decorative graphics.

### 8.3 Primary UI Modules

```text
ResearchHeader
CapabilityStrip
ResearchComposer
UploadedFileList
ResearchProgress
ResearchAnswer
ClaimEvidenceRail
SourceInspector
LimitationList
ReportPanel
DiagnosticsPanel
```

`DiagnosticsPanel` is collapsed by default and contains safe event details.
Raw Provider payloads are never sent to it.

### 8.4 Frontend State

```typescript
type ResearchStatus =
  | "idle"
  | "checking-capabilities"
  | "ready"
  | "running"
  | "completed"
  | "degraded"
  | "failed"
  | "cancelled";

type ResearchStage =
  | "planning"
  | "collecting"
  | "validating"
  | "synthesizing"
  | "reporting";
```

The workbench owns one browser-generated thread UUID, one WebSocket, multiple
uploaded-file records, one terminal-event guard, the current capability
snapshot, progress, result document, and artifact list.

The Start button is disabled only when:

- the query is empty;
- a task is active;
- the WebSocket is not connected;
- a required capability is unavailable;
- a task-start request is pending.

Optional capability failures do not disable Start.

### 8.5 User-Facing Progress

Internal events map to five stages:

```text
正在分析研究问题
正在收集资料
正在核对证据
正在组织研究结论
正在生成报告
```

Provider failures appear as actionable limitations, for example:

```text
实时网络检索暂时失败，本次研究继续使用其他可用来源。
本地知识库尚未就绪，本次回答未包含本地知识证据。
研究模型当前不可用，请检查服务端模型配置后重试。
```

The UI must never display the generic browser error `Network request failed`
when a structured server error is available.

## 9. Migration Strategy

### Stage 1: Model, Web, And Uploads

- Make `agent-research` the default application.
- Add capability health and task admission.
- Build the OpenAI-compatible model adapter.
- Assemble DeepAgents with Web and uploaded-file tools.
- Emit version 2 research events.
- Produce a basic validated research document and all three artifacts.
- Replace the current profile-oriented frontend with the research workspace.
- Preserve internal adapters and their focused regression tests.

### Stage 2: MySQL And Local Knowledge

- Add capability checks and workers for read-only MySQL.
- Add capability checks and a worker for Qdrant Local + FastEmbed.
- Preserve stable row and chunk locators.
- Show per-source readiness, coverage, and limitations in the UI.
- Verify mixed ready/unavailable combinations without live external calls in
  automated tests.

### Stage 3: Complete Citations And Reports

- Require structured claim generation from the model response.
- Validate claim-to-evidence references before delivery.
- Make JSON, React, Markdown, and PDF share schema `3.0.0` identities.
- Add explicit unsupported, unavailable, and unused-source states.
- Add safe Provider failure classification and bounded retry behavior.
- Migrate the frontend to `/api/research-results`.
- Run the full offline contract and security gate.
- Run separately authorized live smoke tests for each real Provider.
- Delete legacy user-facing Profile branches only after acceptance.

## 10. Testing Strategy

Tests use injected fakes for model and Provider behavior by default. Automated
tests must not require credentials or network access.

Nearest ownership tests cover:

- settings and credential laziness;
- capability state resolution;
- task admission;
- Provider error classification;
- read-only SQL;
- local knowledge availability;
- evidence normalization and locator safety;
- event version and ordering;
- exactly one terminal event;
- atomic delivery;
- frontend contract parsing;
- capability-driven Start behavior;
- progress mapping;
- claim/evidence/source rendering;
- limitation rendering;
- responsive layout and keyboard focus.

Cross-module acceptance covers:

```text
question + uploads
  -> fake OpenAI-compatible model
  -> fake or local source adapters
  -> WebSocket progress
  -> validated ResearchDocument
  -> JSON + Markdown + PDF
  -> React result rendering
```

Real LLM, Tavily, MySQL, or other live-data smoke tests remain separately
authorized, explicitly opted in, narrowly scoped, and excluded from the
default test suite.

## 11. Security And Safety Invariants

- Browser code never receives Provider credentials.
- Retrieved Web, database, knowledge, and upload text is untrusted data.
- SQL remains read-only and single-statement with database restrictions.
- Upload and output paths remain thread-scoped and traversal-safe.
- Source links are validated by source kind.
- Events and reports contain no credentials, absolute paths, raw Provider
  responses, or exception representations.
- Provider timeouts and result limits are explicit.
- Task cancellation propagates through Agent and tool execution.
- Only `TaskRegistry` emits terminal task events.
- Delivery either publishes the complete artifact set or reports a limitation;
  it does not expose partial files.

## 12. Removal Gate For Internal Adapters

`tutorial` and `showcase` can be deleted only when all conditions are met:

1. The default application has no user-visible Profile branch.
2. Stage 1-3 automated gates pass.
3. The real `agent-research` path has separately authorized live smoke evidence
   for the enabled Providers.
4. Source identity is consistent across API, WebSocket, React, JSON, Markdown,
   and PDF.
5. Success, optional-source degradation, model failure, cancellation, and
   delivery failure each produce one correct terminal outcome.
6. Security checks prove no secret, absolute path, or raw Provider response is
   exposed.
7. No active test imports a legacy adapter except a designated compatibility
   suite scheduled for deletion in the same package.

Until this gate passes, legacy code is isolated but not restored to the
product interface.

## 13. S3-6 Bounded Live-Recovery Addendum

The first authorized S3-6 combined run proved each enabled source in isolation
but did not complete the four-source research journey. The main graph repeatedly
delegated to expert workers until it terminated without a canonical result or
reports. The recovery preserves the DeepAgents main-agent/expert-worker model;
it does not replace research with a fixed four-step pipeline.

### 13.1 Run Budget Contract

`AgentResearchSettings` owns an immutable `ResearchBudgetSettings` value with
these positive-integer defaults:

| Setting | Environment key | Default | Scope |
|---|---|---:|---|
| Graph recursion limit | `RESEARCH_GRAPH_RECURSION_LIMIT` | 40 | Top-level LangGraph run |
| Main model-call limit | `RESEARCH_MAIN_MODEL_CALL_LIMIT` | 12 | Main agent per run |
| Main worker-call limit | `RESEARCH_MAIN_WORKER_CALL_LIMIT` | 4 | Main agent `task` calls per run |
| Upload-read limit | `RESEARCH_UPLOAD_CALL_LIMIT` | 1 | Main agent upload reads per run |
| Worker model-call limit | `RESEARCH_WORKER_MODEL_CALL_LIMIT` | 4 | Each expert invocation |
| Worker source-tool limit | `RESEARCH_WORKER_TOOL_CALL_LIMIT` | 2 | Each expert invocation |

Invalid, zero, or negative values fail application configuration. The limits
bound cost and termination; they do not promise latency, price, or SLA.

The main graph receives `ModelCallLimitMiddleware` plus tool-specific
`ToolCallLimitMiddleware` instances for `task` and `read_uploaded_file`. Each
expert worker receives its own model and source-tool limit middleware. Limiters
use error behavior so budget exhaustion cannot be mistaken for a successful
answer. The orchestrator also supplies the explicit graph recursion limit as a
last-resort guard.

### 13.2 Stop And Evidence Protocol

The main prompt tells the agent to plan a bounded source pass, avoid repeating
a source after it has usable evidence or an explicit limitation, and stop tool
use before the configured budget. Expert workers use no more than two source
calls and return immediately with the collected findings.

Every successful source tool response includes the exact server-generated
`evidence_id` beside its quote and locator. Retrieved text remains untrusted
data. The main agent must finish with exactly one JSON object shaped as:

```json
{
  "answer": "bounded research answer",
  "claims": [
    {
      "statement": "one factual statement",
      "evidence_ids": ["ev-stable-id"]
    }
  ]
}
```

The model may use only IDs returned by tools. Unknown IDs still fail before
delivery, unsupported statements remain explicit limitations, and the server
continues to own citation normalization and artifact generation.

### 13.3 Safe Exhaustion Classification

Tool-call limit, model-call limit, and graph-recursion exceptions are converted
at the orchestrator boundary to `ResearchBudgetExceeded` with public code
`research-budget-exhausted`. `TaskRegistry` emits one terminal failure with the
fixed Chinese message `研究步骤已达到安全上限，请缩小问题范围后重试`, removes
all partial JSON/Markdown/PDF artifacts, and exposes no raw exception or
Provider response. Provider failures keep their existing model/source codes;
budget exhaustion is not classified as a model outage.

### 13.4 Verification And Live Exit

Automated tests first prove the missing behavior and then cover:

- settings defaults and rejection of invalid budget values;
- main and worker middleware assembly with exact per-run limits;
- explicit recursion configuration and safe exception conversion;
- exactly one safe terminal event plus artifact cleanup on exhaustion;
- Web, MySQL, knowledge, and uploaded-file tool responses carrying valid
  `evidence_id` values;
- final structured claims accepting returned IDs and rejecting invented IDs.

After the affected offline regression surface passes, one newly authorized
S3-6 combined run must complete with uploaded-file, Web, read-only MySQL, and
local-knowledge evidence. Acceptance requires a schema `3.0.0` canonical
result, validated claim/evidence/source identities, exactly the JSON/Markdown/
PDF artifact set, one successful terminal event, safe desktop and mobile
rendering without horizontal overflow, and a bounded evidence record. Fixture
knowledge may prove the adapter and locator path but must not be described as
formal six-document corpus or retrieval-quality acceptance when that corpus is
absent.
