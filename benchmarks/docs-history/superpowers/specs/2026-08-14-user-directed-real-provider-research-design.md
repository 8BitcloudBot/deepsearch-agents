# User-Directed Real-Provider Research Design

**Date:** 2026-08-14

**Status:** Approved design

**Supersedes:** `2026-08-13-agent-research-product-convergence-design.md`

## 1. Objective

Build one user-facing `agent-research` product whose normal path is driven by
real OpenAI-compatible model calls and real user-selected data sources. The
user decides which sources are part of a run. The model decides how to
investigate the question within that choice. The application owns execution,
source-state truth, evidence validation, and report delivery.

The target flow is:

```text
question + source selection + uploaded files
  -> real LLM research plan
  -> application-owned research coordinator
  -> real Web / read-only MySQL / local knowledge / uploaded-file execution
  -> per-source execution outcomes + normalized evidence
  -> real LLM gap review and synthesis
  -> validated claims and citations
  -> WebSocket + React + JSON/Markdown/PDF
```

The product does not expose or assemble tutorial, showcase, mock, fixture, or
offline-demo modes. Deterministic tests remain only where they prove pure
domain behavior, security rules, or Provider adapter contracts. They are not
product modes and do not stand in for real end-to-end acceptance.

## 2. Problems In The Existing Design

The existing request contains only a question and thread ID. It cannot express
which sources the user selected. The runtime therefore lets the main Agent
decide whether and how often to call sources.

That creates four product failures:

1. A source can be repeated or skipped independently of the user's intent.
2. Capability availability, source selection, source execution, zero matches,
   and cited evidence are collapsed into one inferred UI label.
3. Missing optional capabilities are added as limitations even when the user
   did not select them.
4. Model-call, tool-call, timeout, or invalid-citation errors can destroy an
   otherwise useful evidence set and report.

The current free-form top-level `task` loop is therefore not the target
architecture. Adding more prompt instructions or tighter call limits does not
repair the missing product state.

## 3. Confirmed Product Decisions

1. `agent-research` is the only product mode.
2. The real OpenAI-compatible LLM participates in planning, expert research,
   evidence-gap review, and final synthesis.
3. Web is selected by default when ready and may be turned off by the user.
4. Read-only MySQL and local knowledge are unselected by default and are used
   only when the user selects them.
5. Successfully uploaded files are automatically selected for the current
   research run and may be removed before start.
6. A run with no selected external source is allowed. It is explicitly marked
   as LLM-only and contains no externally validated citations.
7. An unselected source is not a limitation. No uploaded file is shown as
   `无参考`, not as unavailable or degraded.
8. A selected source must produce an explicit execution outcome. The Agent may
   not silently skip it.
9. A successful retrieval with zero relevant results is `无相关数据命中`, not a
   Provider failure.
10. Search depth is driven by unresolved evidence questions. Safety budgets are
    outer guards, not the research strategy.
11. Invalid model-produced evidence references are rejected without discarding
    valid evidence or failing the entire run.
12. Product-level tutorial, showcase, mock, fixture, and offline-demo assembly
    and complete simulated research journeys are deleted.
13. Pure domain, security, and Provider-adapter contract tests remain. Core
    integration and browser acceptance use real configured Providers.

## 4. Ownership Model

The system separates decisions by owner:

| Decision | Owner |
|---|---|
| Which source kinds are allowed in the run | User |
| Which uploaded files belong to the run | User and session workspace |
| Which evidence questions must be answered | Real planning LLM |
| Which selected source handles each evidence question | Planning LLM, validated by the coordinator |
| Whether every selected source was attempted | Application coordinator |
| How to formulate Web, SQL, or knowledge queries | Real expert worker |
| Whether a result is a hit, no-match, unavailable, or failed | Source adapter and coordinator |
| Whether evidence is safe and citation-addressable | Application evidence domain |
| Whether more retrieval is needed | Real gap-review LLM over coordinator-owned coverage state |
| Whether a claim may cite an evidence ID | Application validator |
| Artifact rendering and publication | Application delivery module |

The model retains research judgment. The application no longer delegates
execution truth or source-state truth to model behavior.

## 5. User Request Contract

The product request becomes a research-specific value object:

```python
@dataclass(frozen=True)
class ResearchSourceSelection:
    web: bool = True
    mysql: bool = False
    knowledge: bool = False

@dataclass(frozen=True)
class ResearchRequest:
    thread_id: str
    query: str
    sources: ResearchSourceSelection
    uploaded_files: tuple[str, ...]
```

The server validates thread ownership and snapshots the selected uploads before
task creation. A filename that was not uploaded to the thread is rejected.
Capability readiness does not change the user's selection. If readiness changes
between composition and execution, the run records `unavailable` and continues
with the remaining selected sources.

Derived research modes are:

```text
llm-only
llm+web
llm+uploads
llm+selected-sources
```

These are result descriptions, not Profiles or alternate runtimes.

## 6. Research Plan

The real planning LLM returns a validated `ResearchPlan` before source use:

```python
@dataclass(frozen=True)
class EvidenceQuestion:
    question_id: str
    question: str
    selected_sources: tuple[SourceKind, ...]
    required: bool

@dataclass(frozen=True)
class ResearchPlan:
    objective: str
    evidence_questions: tuple[EvidenceQuestion, ...]
```

The coordinator rejects source kinds that the user did not select. It also
ensures every selected source receives at least one applicable evidence
question or one explicit general relevance probe. This prevents a selected
MySQL or knowledge source from being silently ignored by the plan.

Plan validation is structural. It does not impose a fixed number of Web
searches. Empty or malformed plans receive one bounded model retry; a second
invalid plan produces a specific planning failure.

## 7. Source Execution Record

Availability and run execution are separate concepts. Health continues to
describe whether a capability can be attempted. Every run owns immutable
`SourceRun` records describing what actually happened.

```python
SourceExecutionStatus = Literal[
    "not-selected",
    "no-reference",
    "planned",
    "running",
    "matched",
    "no-match",
    "unavailable",
    "failed",
]

@dataclass(frozen=True)
class SourceRun:
    source_kind: SourceKind
    selected: bool
    status: SourceExecutionStatus
    attempt_count: int
    query_count: int
    hit_count: int
    evidence_count: int
    cited_evidence_count: int
    safe_message: str
    uploaded_file: str | None = None
```

Invariants:

- `not-selected` is never a limitation.
- Uploads use `no-reference` when no file is present.
- `no-match` means execution succeeded and returned no acceptable evidence.
- `unavailable` means the selected capability could not be attempted.
- `failed` means an attempted Provider or adapter operation failed.
- `matched` may still have zero cited evidence when retrieved material was not
  used by the final claims.
- Counts are coordinator-owned and cannot be supplied by the model.

## 8. Orchestration Architecture

Replace the free-form top-level DeepAgents `task` loop with an explicit graph:

```text
admit
  -> plan with the real main LLM
  -> validate plan against user selection
  -> execute selected source workers
  -> update SourceRun ledger and evidence pool
  -> review evidence coverage with the real main LLM
  -> run targeted source refinements for uncovered questions
  -> synthesize with the real main LLM
  -> validate claims
  -> deliver
```

The graph remains a main-agent and expert-worker research system. Its topology
is application-owned, so a model cannot create an unbounded fan-out of
identical workers. Each expert worker receives only its assigned evidence
questions, its source adapter, the shared deduplication ledger, and the
remaining outer safety budget.

### 8.1 Web Expert

The Web expert uses the real LLM to formulate searches for assigned evidence
questions. It may refine searches only for questions whose coverage remains
open. The coordinator deduplicates normalized queries, canonical URLs, and
content hashes across the whole run.

There is no fixed target search count. The worker stops when required evidence
questions are covered or when the outer run budget is exhausted. Exhaustion
with usable evidence produces a degraded result with an explicit coverage gap;
it does not delete evidence or reports.

### 8.2 MySQL Expert

The MySQL expert is created only when the user selects MySQL and the capability
is configured. It uses the real LLM to inspect allowed schema metadata and
formulate a single-statement read-only query. Existing allowlists, parser
checks, row limits, and stable row locators remain mandatory.

Zero rows produce `no-match`. Policy rejection and Provider failure remain
distinct outcomes.

### 8.3 Knowledge Expert

The knowledge expert is created only when selected. It uses the real LLM to
formulate retrieval queries against the configured local index. Successful
retrieval below the accepted relevance threshold produces `no-match`.
Unavailable index state and adapter failure are separate outcomes.

### 8.4 Uploaded Files

Uploaded files do not require an autonomous tool-selection loop. The
coordinator reads every selected thread-owned file through the safe upload
adapter, creates span evidence, and supplies it to the real planning and
synthesis flow. Each file receives its own `SourceRun` record.

## 9. Evidence And Synthesis

The evidence collector remains the only owner of source, locator, evidence ID,
and content-hash creation. Provider and model output are untrusted input.

The real synthesis LLM receives:

- the validated research plan;
- selected-source execution outcomes;
- normalized evidence records;
- unresolved evidence questions;
- explicit no-match, unavailable, and failed outcomes.

It returns an answer and claims referencing collector-owned evidence IDs. The
validator keeps only known IDs. A claim with no known evidence becomes an
unsupported claim and is not rendered with a citation badge. Other valid
claims and evidence remain deliverable.

A structurally invalid synthesis receives one bounded model retry. If synthesis
still fails, the task emits a specific model-result failure while preserving
safe source-run progress for the UI. It never emits a generic `research_failed`
when a classified failure is available.

## 10. Result Contract

The revised canonical document uses schema `4.0.0` because source-selection,
plan, and execution semantics are new required fields rather than compatible
extensions to schema `3.0.0`.

```python
@dataclass(frozen=True)
class ResearchDocument:
    schema_version: Literal["4.0.0"]
    thread_id: str
    query: str
    research_mode: str
    plan: ResearchPlan
    source_runs: tuple[SourceRun, ...]
    answer: str
    claims: tuple[ResearchClaim, ...]
    sources: tuple[ResearchSource, ...]
    evidence: tuple[ResearchEvidence, ...]
    limitations: tuple[ResearchLimitation, ...]
    artifacts: tuple[str, str, str]
```

The exact artifacts remain:

```text
research-citations.json
research-report.md
research-report.pdf
```

All delivery surfaces use the same plan, source-run, claim, evidence, and
limitation identities.

## 11. Completion Semantics

The task terminal remains exactly one of completed, failed, or cancelled. A
completed document carries a result quality status:

| Result status | Meaning |
|---|---|
| `completed` | The requested research path executed and synthesis completed. |
| `completed` with `llm-only` mode | The user intentionally selected no external reference. |
| `completed` with `no-match` source runs | Selected retrieval succeeded but found no relevant data. |
| `degraded` | A selected source was unavailable or failed, required coverage remains open, or unsupported claims were removed. |
| `failed` terminal | Planning/synthesis cannot produce a safe result, a required capability fails, or atomic delivery fails. |

No-reference, not-selected, and successful no-match outcomes do not by
themselves degrade a result. A no-match report explains what was searched and
that no relevant data was found; it does not fabricate an answer or citation.

## 12. HTTP And WebSocket Changes

`POST /api/task` accepts:

```json
{
  "thread_id": "uuid",
  "query": "research question",
  "sources": {
    "web": true,
    "mysql": false,
    "knowledge": false
  },
  "uploaded_files": ["notes.pdf"]
}
```

The WebSocket lifecycle adds source-semantic events:

```text
research_plan_created
source_planned
source_started
source_matched
source_no_match
source_unavailable
source_failed
source_completed
coverage_reviewed
answer_draft_ready
report_created
task_completed
task_failed
task_cancelled
```

Event data contains only stable IDs, source kind, counts, status, and safe
messages. It never contains credentials, raw Provider output, SQL secrets,
absolute paths, or exception text.

## 13. Frontend Experience

The composer adds a `研究来源` control:

- Web toggle: on by default when ready.
- Structured-data toggle: off by default.
- Local-knowledge toggle: off by default.
- Unavailable optional sources: disabled with a fixed reason.
- Uploaded files: automatically selected after upload and removable before
  start.
- Empty upload state: `会话文件：无参考`.

Before start, the UI shows one plain-language summary such as:

```text
本次研究：真实研究模型 + 实时网络 + 2 个参考文件
```

With no external source it shows:

```text
本次研究：仅使用研究模型，不包含外部可验证证据
```

During execution, the progress view is plan- and source-oriented. It does not
repeat generic messages for each tool call. The result view reads `SourceRun`
directly and can distinguish:

```text
未选择
无参考
正在检索
命中 8 条，其中 3 条用于结论
已检索，无相关数据命中
当前不可用
检索失败
```

The capability strip remains readiness-only. It is never reused as the result
coverage display. Generic failure copy is replaced by classified actionable
messages and a safe collapsed diagnostic record.

## 14. Real-Provider Product Boundary

Remove from default and test assembly:

- tutorial and showcase runtime selection;
- mock Provider bundles and product Profiles;
- deterministic research demo servers and scenario switches;
- fake/local browser journeys that generate complete simulated research
  reports;
- product documentation that presents offline fixtures as a usable mode.

Retain only:

- real OpenAI-compatible model assembly;
- real Tavily, read-only MySQL, local knowledge, and upload adapters;
- pure domain and security tests;
- adapter contract tests with minimal test doubles;
- real-provider integration and browser acceptance commands.

Test doubles must not be reachable from production assembly and must not
produce a user-facing research experience.

## 15. Verification Strategy

Credential-free automated checks are limited to deterministic behavior that
cannot be meaningfully proven by a live model:

- request and source-selection validation;
- source-run state transitions;
- query/URL/content deduplication;
- read-only SQL and path safety;
- evidence identity, redaction, and citation filtering;
- exactly one terminal event;
- atomic artifact delivery;
- frontend parsing and rendering of every source-run state;
- Provider adapter request/response and error classification.

Real acceptance is the authority for product behavior. It covers:

1. real LLM + Web, no upload;
2. real LLM + Web + uploaded files;
3. user-selected read-only MySQL;
4. user-selected local knowledge;
5. a user-selected mixed-source run;
6. intentional LLM-only research;
7. real zero-match behavior;
8. classified Provider failure, cancellation, and result validation;
9. desktop and mobile browser completion with JSON, Markdown, and PDF.

Acceptance records actual selected sources, plan questions, source-run
outcomes, evidence counts, terminal state, and artifacts. It does not infer
quality, cost, latency, or production readiness beyond the measured run.

## 16. Implementation Order

Implementation proceeds by dependency, not by UI appearance:

1. Replace the request and document domain with `ResearchRequest`,
   `ResearchPlan`, `SourceRun`, and schema `4.0.0`.
2. Add source-selection HTTP validation and source-semantic WebSocket events.
3. Build the explicit coordinator and real planning/synthesis seams.
4. Move Web, MySQL, knowledge, and uploaded-file execution behind
   coordinator-owned expert interfaces.
5. Add adaptive Web coverage and run-wide deduplication.
6. Change citation parsing from whole-run failure to claim-level rejection.
7. Rebuild the React composer, progress, coverage, and result states from the
   new contracts.
8. Remove mock/offline product assembly and complete simulated journeys.
9. Run focused deterministic gates, then the real-provider acceptance matrix.
10. Update canonical status only from the verified implementation state.

No step restores a visible Profile or alternate runtime. Legacy deletion must
not remove pure domain safety tests that still protect the real product.

## 17. Exit Criteria

The revised convergence package is complete only when:

- the user can select sources exactly as specified;
- no upload displays `无参考`;
- selected MySQL and knowledge runs report matched, no-match, unavailable, or
  failed truthfully;
- unselected sources never appear as limitations;
- Web retrieval adapts to evidence gaps without duplicate worker fan-out;
- LLM-only research is explicit and contains no fabricated citations;
- invalid model citations do not destroy valid results;
- React, WebSocket, JSON, Markdown, and PDF share schema `4.0.0` source-run and
  evidence identities;
- the mock/offline product and complete demo paths are absent;
- pure domain and adapter checks pass;
- the real-provider acceptance matrix completes with classified outcomes;
- no push, release, publication, or deployment is performed without separate
  authorization.
