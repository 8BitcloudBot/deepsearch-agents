# Phase 2A Implementation Addendum

**Status:** Accepted and closed
**Date:** 2026-08-07
**Applies to:** Phase 2A — Demo Closure
**Accepted backend baseline:** `198b0c7`
**Target release:** `v0.1-tutorial-parity`

## 1. Purpose And Authority

This addendum records the accepted implementation boundary for Phase 2A. It
translated the long-range v3 design into the repository contracts used to
complete the tutorial closure without pulling Phase 3-9 capabilities forward.

Instruction precedence for Phase 2A is:

1. [`../phase-status.md`](../phase-status.md)
2. this addendum
3. [`phase-2-tutorial-parity.md`](phase-2-tutorial-parity.md)
4. accepted evidence in [`../verification/phase-2-evidence.md`](../verification/phase-2-evidence.md)
5. the v3 design and historical plans as background only

When a long-range design statement conflicts with this addendum, this addendum
controls Phase 2A. Phase 7+ API, persistence, recovery, approval and governance
designs are not current implementation instructions.

## 2. Current Baseline

At `198b0c7`, the Phase 2A backend vertical closure is accepted. Fresh evidence
proves:

- upload returns success for a thread-scoped constraint file;
- task creation returns `202`;
- Web, Catalog and Knowledge Provider tool events are all observed;
- exactly one terminal event is emitted;
- `tutorial-report.md` and `tutorial-report.pdf` are generated;
- `/api/files` lists both reports;
- `/api/download` returns both reports and the PDF begins with `%PDF`;
- the uploaded unique marker is present in the downloaded Markdown;
- thread isolation, relative artifact paths and terminal/report error redaction
  pass their responsibility-boundary tests.

The React frontend is accepted in the Phase 2A checkpoint working tree. It
implements the thread-scoped upload, task controls, complete live event
timeline, terminal states, Markdown preview and Markdown/PDF downloads. The
frontend suite, production build and desktop/mobile browser smoke pass. A
minimal local-development CORS allowlist permits the documented Vite origins.
Phase 2A as a whole is accepted; Phase 2B owns subsequent safety hardening.

## 3. Scope Freeze

### 3.1 Required In Phase 2A

- a React research workbench, not a marketing page;
- one stable client-generated `thread_id` per active demonstration;
- constraint-file upload;
- research query submission;
- WebSocket connection and event timeline;
- visible running, success, failure and cancellation states;
- cancellation of the active task;
- Markdown report preview;
- Markdown and PDF artifact listing and download;
- mock-mode quick start without model keys or external network;
- frontend unit/component tests, lint and production build;
- desktop and mobile browser smoke;
- documentation and evidence synchronized with the accepted behavior.

### 3.2 Explicitly Deferred

The following are not Phase 2A work:

- task, event or checkpoint persistence;
- event replay, `last_event_id` or reconnect backfill;
- service-restart recovery or resume;
- approval workflows;
- token, cost or concurrency governance;
- Claim/Evidence extraction or citation verification;
- evaluation datasets or orchestration experiments;
- authentication, tenancy or production authorization;
- migration to the future plural `/api/tasks` and `/api/artifacts` API;
- durable browser history;
- final AI Agent research-domain migration.

The implementation plan must reject changes whose only purpose is a deferred
capability.

## 4. Frozen Backend Contracts

Phase 2A keeps the accepted tutorial API:

| Method | Path | Phase 2A behavior |
| --- | --- | --- |
| `GET` | `/health` | Returns non-secret provider/runtime modes |
| `POST` | `/api/upload` | Multipart upload with `thread_id` and `files` |
| `POST` | `/api/task` | Starts one task for `{query, thread_id}` |
| `POST` | `/api/task/{thread_id}/cancel` | Cancels the active task |
| `GET` | `/api/files?thread_id=...` | Lists current-thread output files |
| `GET` | `/api/download?thread_id=...&path=...` | Downloads one contained relative file |
| `WS` | `/ws/{thread_id}` | Live event stream plus ping/pong |

The frontend must not rename these endpoints or add a compatibility API. The
future `/api/tasks/{task_id}` and `/api/artifacts/{artifact_id}` design begins
only in its designated later phase.

### 4.1 Thread Identity

- The browser creates the thread identifier with `crypto.randomUUID()`.
- The same UUID is used for upload, WebSocket, task start, cancel, file list and
  download.
- Starting a new demonstration creates a new UUID and clears all prior UI state.
- The UI must not use filenames, query text or event messages as identifiers.

## 5. Event Contract

The frontend consumes `TutorialEvent` version 1:

```text
version
sequence
thread_id
type
message
data
timestamp
```

Allowed event types are:

```text
task_started
agent_started
agent_completed
tool_started
tool_completed
artifact_created
task_completed
task_cancelled
task_failed
```

Phase 2A rules:

- `sequence` is the ordering field; there is no persistent `event_id`.
- Events are live-only and are not replayed after disconnect.
- A WebSocket disconnect does not cancel the backend task.
- Ping/pong messages are transport heartbeats, not timeline events.
- Queue overflow closes the connection with code `1013`.
- Unknown event versions or malformed JSON produce a visible client error; the
  client must not infer success from raw text.
- The client deduplicates timeline items by `(thread_id, sequence)`.

## 6. Task Lifecycle

The in-memory `TaskRegistry` remains the sole owner of task lifecycle events.

- One `thread_id` may have at most one active task.
- Duplicate active starts remain an HTTP `409`.
- Start emits `task_started`.
- Normal completion emits exactly one `task_completed`.
- Ordinary failure emits exactly one `task_failed`.
- Cancellation, including cancellation before coroutine entry, emits exactly
  one `task_cancelled`.
- Terminal event payloads stay empty/non-sensitive.
- Completed tasks are removed from the in-memory registry.
- No lifecycle state survives process restart.

The frontend terminal mapping is:

| Event | UI state |
| --- | --- |
| `task_started` | `running` |
| agent/tool/artifact events | retain `running`, append/update display |
| `task_completed` | `success` |
| `task_failed` | `failed` |
| `task_cancelled` | `cancelled` |

Once a terminal event is accepted, later events must not change the terminal
state.

## 7. Provider Boundary

The Phase 2A closure requires three Provider families:

| Family | Mock evidence event |
| --- | --- |
| Web | `internet_search` |
| Catalog | `list_sql_tables` |
| Knowledge | `list_knowledge_assistants` |

Rules:

- `mock/mock/mock` is the default demonstration and test configuration.
- Mock mode requires no model key and no external network.
- External Tavily, MySQL, RAGFlow or model smoke is optional evidence and must
  not block the offline workbench.
- Missing external credentials must produce an explicit skip or startup error,
  never silent provider substitution.
- The implementation must not remove or weaken the three-Provider E2E
  assertions.

## 8. File And Artifact Contract

Required final artifacts are:

```text
tutorial-report.md
tutorial-report.pdf
```

The workbench must:

- upload at least one supported constraint file before enabling task start;
- display accepted filename and size from the upload response;
- refresh `/api/files` after successful completion;
- show only the current thread's artifact list;
- preview Markdown as safe plain text for Phase 2A;
- download Markdown and PDF through `/api/download`;
- never render report content with `dangerouslySetInnerHTML`;
- never construct a filesystem path outside the path returned by `/api/files`.

PDF inline rendering, rich Markdown HTML, report editing and artifact IDs are
deferred.

## 9. React Workbench Design

### 9.1 Required Surfaces

1. **Session header** — current thread identifier, provider/runtime modes from
   `/health`, and a reset/new-session action.
2. **Constraint upload** — supported file chooser, upload status and errors.
3. **Research composer** — query input, start button and cancel button.
4. **Run status** — idle, uploading, ready, running, success, failed,
   cancelled and connection-error states.
5. **Event timeline** — ordered task, agent, tool and artifact events.
6. **Artifact panel** — Markdown preview and Markdown/PDF download actions.

### 9.2 Interaction Order

```text
create thread
→ connect WebSocket
→ upload constraint file
→ submit research query
→ consume live events
→ receive exactly one terminal state
→ refresh artifact list
→ preview Markdown / download Markdown and PDF
```

The WebSocket should be connected before task submission so the live-only bus
does not lose early lifecycle events.

### 9.3 UI State Rules

- A new session clears query, upload, timeline, terminal state and artifacts.
- A new run clears the previous run's terminal/error/artifact display before
  submitting.
- The start button is disabled without an uploaded file, an empty query, while
  uploading, or while a task is active.
- The cancel button is available only while a task is active.
- Failed and cancelled runs cannot retain a prior success preview.
- WebSocket disconnect is shown separately from backend task failure.
- The layout remains usable at 1440px and 375px without horizontal page scroll.

### 9.4 Dependency Boundary

Use the existing React/Vite/TypeScript/Vitest stack. A new runtime dependency
requires a concrete Phase 2A need and explicit plan justification. Phase 2A
does not require a component framework, state-management library, charting
library or Markdown-to-HTML renderer.

## 10. Error And Security Behavior

- API errors display a stable user-facing message and HTTP status context.
- Provider raw responses, exception reprs, absolute paths and credentials must
  not enter the browser state or timeline.
- Uploaded content remains untrusted data and is never treated as UI markup or
  executable instruction.
- The browser never stores provider keys.
- File download uses only server-returned relative paths and the current UUID.
- Cancellation `404` is displayed as "no active task" rather than success.
- WebSocket close `1013` is displayed as a slow-consumer/stream interruption.
- The UI may offer a new session after connection failure, but Phase 2A does
  not promise event replay or task recovery.

## 11. Implementation Slices

The implementation plan should use vertical slices and accept each before the
next begins.

### Slice F1 — Client Contracts And Static Shell

- typed API and event contracts;
- thread creation and health display;
- responsive workbench shell;
- tests for initial, reset and invalid-response states.

### Slice F2 — Upload And Task Controls

- multipart upload;
- query submission;
- duplicate/start/cancel error handling;
- tests for control enablement and stale-state clearing.

### Slice F3 — WebSocket Timeline And Terminal States

- connect before task start;
- event validation, ordering and deduplication;
- running/success/failed/cancelled/connection-error states;
- tests for exactly-one-terminal client behavior and close `1013`.

### Slice F4 — Artifact Preview And Download

- refresh file list after success;
- safe Markdown text preview;
- Markdown/PDF download;
- tests for thread scoping, missing artifacts and old-result clearing.

### Slice F5 — Integrated Evidence

- frontend full test/lint/build;
- backend regression gates;
- mock quick start;
- desktop/mobile browser smoke;
- README, phase status and verification evidence updates.

Do not combine all five slices into one uncontrolled Reasonix writing node.

## 12. Acceptance Matrix

### 12.1 Backend Regression

```bash
.venv/bin/python -m pytest tests/e2e/phase2/test_tutorial_closure.py -q
.venv/bin/python -m pytest tests/integration/phase2 tests/unit/phase2 -q
.venv/bin/ruff check app tests
.venv/bin/ruff format --check app tests
.venv/bin/pre-commit run --all-files
git diff --check
```

### 12.2 Frontend

```bash
pnpm --dir frontend exec vitest run
pnpm --dir frontend exec eslint src
pnpm --dir frontend run build
```

Frontend tests must cover:

- initial and reset state;
- successful upload;
- upload rejection;
- task start and duplicate/start failure;
- ordered Provider events;
- success, failure and cancellation;
- WebSocket disconnect and overflow close;
- Markdown preview and both downloads;
- stale success clearing on a new or failed run.

### 12.3 Browser Smoke

At both 1440px and 375px:

1. start the mock backend and Vite frontend;
2. create a session and upload a constraint file;
3. submit a research query;
4. observe Web, Catalog and Knowledge activity;
5. observe one successful terminal state;
6. preview Markdown;
7. download Markdown and PDF;
8. run a cancellation or controlled failure path;
9. confirm no stale successful artifact remains after failure.

## 13. Phase 2A Definition Of Done

Phase 2A is complete only when:

- the accepted backend E2E remains green;
- all three Provider families are visible in the closure;
- exactly-one-terminal behavior remains green;
- the React workbench completes upload-to-report delivery;
- Markdown and PDF are both accessible;
- frontend tests, lint and build pass;
- the offline mock quick start is reproducible;
- desktop and mobile browser smoke pass;
- README, `phase-status.md` and evidence describe the same current HEAD;
- known limitations explicitly state live-only events and in-memory tasks;
- user acceptance occurs before creation of `v0.1-tutorial-parity`.

## 14. Implementation-Plan Review Checklist

The completed Reasonix execution used the following controls:

- cites this addendum and the canonical status, not a legacy handoff;
- begins from the current Git status and HEAD;
- preserves the accepted backend instead of redesigning it;
- does not rename the Phase 2A API;
- does not implement persistence, replay, recovery or approvals;
- splits F1-F5 into independently accepted nodes;
- gives each node an exact file whitelist and observable test commands;
- preserves one writer per worktree;
- requires Reasonix to use a fresh run, never resume/continue/copy;
- leaves commit, push and release tag creation outside implementation nodes.

## 15. Closed Decisions

The following accepted Phase 2A defaults remain frozen and can be revisited in
their designated later phases:

- plain-text Markdown preview instead of rendered HTML;
- PDF download instead of inline PDF preview;
- no frontend persistence;
- no automatic WebSocket reconnect/replay promise;
- no new UI framework or global state library;
- client-generated UUID thread identity;
- mock providers as the default demonstration.
