# Phase 2B Safety Hardening Implementation Plan

> **For agentic workers:** Execute B1 through B8 as separate fresh Reasonix
> nodes. Codex reviews the complete diff and independently reruns each node's
> acceptance commands before the next node starts.

**Goal:** Harden the accepted Phase 2A tutorial closure at its highest-risk
task, event, WebSocket, file, Provider and error-redaction boundaries without
adding persistence, replay, authentication or governance.

**Architecture:** Keep `TaskRegistry` as the sole lifecycle owner,
`InMemoryEventBus` as a bounded live-only bus, `SessionWorkspace` as the path
containment boundary, and the existing Provider adapters as the external I/O
boundary. Add or strengthen tests at the closest responsibility boundary;
change production code only when a focused RED test proves a real defect.

**Tech Stack:** Python 3.12, asyncio, FastAPI/Starlette, Pydantic, pytest,
Ruff, pre-commit, existing React/Vitest regression suite.

## Execution Status

| Node | Status | Evidence |
|---|---|---|
| B1 — Cancellation Before Coroutine Entry | accepted | 7 focused tests; public-subscription proof; no production change |
| B2 — Active Cancellation And Terminal Ownership | accepted | 14 focused tests; active/repeated cancellation and normal terminal ownership; duplicate teardown clean |
| B3 — WebSocket Disconnect And Slow Consumer | accepted | 48 focused tests; disconnect, overflow and subscriber cleanup isolated |
| B4 — HTTP Negative Contracts And Thread Isolation | accepted | 104 focused tests; negative HTTP, isolation and containment boundaries |
| B5 — File Parsing And Atomic Report Cleanup | accepted (B8 re-verified) | 77 file_reader/reports tests; xlsx parsed from binary file object (extension-independent); atomic cleanup proven |
| B6 — Provider Failure Redaction And Cleanup | accepted (B8 re-verified) | 42 external-adapter/provider/runtime tests; stable operation names, redacted SDK errors, ai-only answer collection |
| B7 — Test Responsibility And Brittleness Cleanup | accepted (B8 re-verified) | 124 lines removed from test_remediation_2; full phase2 suite 355 passed / 9 skipped |
| B8 — Integrated Safety Acceptance | accepted | Codex independent rerun and refreshed `.secrets.baseline` passed all gates |

## Global Constraints

- Baseline checkpoint is commit `1d6166c`.
- Preserve the accepted Phase 2A API and `TutorialEvent` version 1.
- Do not add persistence, replay, recovery, authentication, approval, cost or
  concurrency governance.
- Do not weaken the three-Provider E2E assertions or exactly-one-terminal
  contract.
- Terminal payloads remain empty and non-sensitive.
- One Reasonix writer runs in this worktree at a time.
- Every node uses a fresh `reasonix run`; never use continue/resume/copy.
- Every behavior change follows RED → GREEN.
- No dependency additions, commit, push, tag or release action inside Reasonix.
- `.reasonix/` is not project source and must never be read, modified or added.

---

## B1 — Cancellation Before Coroutine Entry — Accepted

**Goal:** Prove that cancelling immediately after `start()` emits exactly one
`task_cancelled`, removes the registry entry and never emits success/failure.

**Allowed files:**

- `app/api/tasks.py`
- `tests/unit/phase2/test_task_registry.py`

**Steps:**

- [ ] Add a focused test that calls `start()` and `cancel()` before the runtime
  coroutine enters, then collects lifecycle events.
- [ ] Run the focused test and record RED if current behavior is defective.
- [ ] Make the smallest lifecycle fix, if required.
- [ ] Run `tests/unit/phase2/test_task_registry.py -q` and confirm one
  `task_started`, one `task_cancelled`, zero other terminal events and
  `active_count == 0`.

**Acceptance:**

```bash
.venv/bin/python -m pytest tests/unit/phase2/test_task_registry.py -q
.venv/bin/ruff check app/api/tasks.py tests/unit/phase2/test_task_registry.py
.venv/bin/ruff format --check app/api/tasks.py tests/unit/phase2/test_task_registry.py
git diff --check
```

## B2 — Active Cancellation And Terminal Ownership — Accepted

**Goal:** Prove active cancellation, ordinary failure and successful
completion each emit exactly one terminal event and always clean the registry.

**Allowed files:**

- `app/api/tasks.py`
- `tests/unit/phase2/test_task_registry.py`
- `tests/integration/phase2/test_mock_runtime.py`

**Steps:**

- [ ] Add deterministic blocking, failing and completing runtime doubles.
- [ ] Assert cancellation returns `cancelled` or `cancelling` only while active.
- [ ] Assert repeated cancellation cannot create a second terminal event.
- [ ] Assert `BaseException` subclasses are not converted into false success.
- [ ] Apply the smallest production fix only after a focused RED result.

**Acceptance:**

```bash
.venv/bin/python -m pytest tests/unit/phase2/test_task_registry.py tests/integration/phase2/test_mock_runtime.py -q
.venv/bin/ruff check app/api/tasks.py tests/unit/phase2/test_task_registry.py tests/integration/phase2/test_mock_runtime.py
.venv/bin/ruff format --check app/api/tasks.py tests/unit/phase2/test_task_registry.py tests/integration/phase2/test_mock_runtime.py
git diff --check
```

## B3 — WebSocket Disconnect And Slow Consumer — Accepted

**Goal:** Prove disconnect only removes the subscriber, never cancels the
backend task, and queue overflow closes that subscriber with code `1013` while
other subscribers and future subscriptions remain usable.

**Allowed files:**

- `app/api/events.py`
- `app/api/server.py`
- `tests/unit/phase2/test_events.py`
- `tests/integration/phase2/test_websocket_flow.py`

**Steps:**

- [ ] Add a WebSocket disconnect test with a blocking runtime and assert the
  task remains active until explicitly released or cancelled.
- [ ] Add an overflow test that fills one bounded subscription and observes
  close code `1013` without affecting another thread/subscriber.
- [ ] Assert subscription cleanup after normal close, overflow and exception.
- [ ] Fix only the event/server boundary demonstrated by RED.

**Acceptance:**

```bash
.venv/bin/python -m pytest tests/unit/phase2/test_events.py tests/integration/phase2/test_websocket_flow.py -q
.venv/bin/ruff check app/api/events.py app/api/server.py tests/unit/phase2/test_events.py tests/integration/phase2/test_websocket_flow.py
.venv/bin/ruff format --check app/api/events.py app/api/server.py tests/unit/phase2/test_events.py tests/integration/phase2/test_websocket_flow.py
git diff --check
```

## B4 — HTTP Negative Contracts And Thread Isolation — Accepted

**Goal:** Harden malformed IDs, duplicate starts, missing cancellation, upload
rejection, cross-thread listing and download containment at the HTTP boundary.

**Allowed files:**

- `app/api/server.py`
- `app/api/schemas.py`
- `app/tools/files.py`
- `tests/integration/phase2/test_api_contract.py`
- `tests/unit/phase2/test_workspace.py`

**Steps:**

- [ ] Add table-driven HTTP tests for malformed UUIDs, duplicate `409`, cancel
  `404`, unsupported/forged/oversized uploads and unsafe download paths.
- [ ] Create two thread workspaces and prove neither list nor download endpoint
  can expose the other's files.
- [ ] Assert error details contain no resolved absolute path.
- [ ] Fix only the responsible validation/containment boundary after RED.

**Acceptance:**

```bash
.venv/bin/python -m pytest tests/integration/phase2/test_api_contract.py tests/unit/phase2/test_workspace.py -q
.venv/bin/ruff check app/api/server.py app/api/schemas.py app/tools/files.py tests/integration/phase2/test_api_contract.py tests/unit/phase2/test_workspace.py
.venv/bin/ruff format --check app/api/server.py app/api/schemas.py app/tools/files.py tests/integration/phase2/test_api_contract.py tests/unit/phase2/test_workspace.py
git diff --check
```

## B5 — File Parsing And Atomic Report Cleanup

**Goal:** Prove failed parsing/report generation leaves no partial final file,
unsafe fixed temp symlinks cannot escape containment, and later successful runs
replace reports atomically.

**Allowed files:**

- `app/tools/files.py`
- `app/tools/reports.py`
- `tests/unit/phase2/test_file_reader.py`
- `tests/unit/phase2/test_reports.py`
- `tests/unit/phase2/test_workspace.py`

**Steps:**

- [ ] Add focused failure-injection tests for supported parsers and both report
  generators.
- [ ] Assert temporary files are removed and existing valid final reports are
  not replaced by a failed write.
- [ ] Assert symlink/temp-name attacks cannot modify an outside sentinel.
- [ ] Implement only defects demonstrated by RED.

**Acceptance:**

```bash
.venv/bin/python -m pytest tests/unit/phase2/test_file_reader.py tests/unit/phase2/test_reports.py tests/unit/phase2/test_workspace.py -q
.venv/bin/ruff check app/tools/files.py app/tools/reports.py tests/unit/phase2/test_file_reader.py tests/unit/phase2/test_reports.py tests/unit/phase2/test_workspace.py
.venv/bin/ruff format --check app/tools/files.py app/tools/reports.py tests/unit/phase2/test_file_reader.py tests/unit/phase2/test_reports.py tests/unit/phase2/test_workspace.py
git diff --check
```

## B6 — Provider Failure Redaction And Cleanup

**Goal:** Prove Provider/model/report failures clean transient resources and do
not place credentials, raw responses, exception reprs or absolute paths in
events, HTTP responses or generated reports.

**Allowed files:**

- `app/agent/runtime.py`
- `app/providers/factory.py`
- `app/providers/tavily.py`
- `app/providers/ragflow.py`
- `app/providers/mysql.py`
- `app/tools/knowledge.py`
- `tests/unit/phase2/test_external_adapters.py`
- `tests/unit/phase2/test_provider_factories.py`
- `tests/unit/phase2/test_runtime_events.py`
- `tests/integration/phase2/test_mock_runtime.py`

**Steps:**

- [ ] Inject stable fake Provider failures containing a fake key, raw payload
  marker and absolute-path marker.
- [ ] Assert RAGFlow sessions/connections are cleaned on success and failure.
- [ ] Assert runtime/tool events expose only stable operation names and empty
  terminal payloads.
- [ ] Assert reports do not contain the injected sensitive markers.
- [ ] Apply the smallest adapter/runtime fix after RED.

**Acceptance:**

```bash
.venv/bin/python -m pytest tests/unit/phase2/test_external_adapters.py tests/unit/phase2/test_provider_factories.py tests/unit/phase2/test_runtime_events.py tests/integration/phase2/test_mock_runtime.py -q
.venv/bin/ruff check app/agent/runtime.py app/providers app/tools/knowledge.py tests/unit/phase2/test_external_adapters.py tests/unit/phase2/test_provider_factories.py tests/unit/phase2/test_runtime_events.py tests/integration/phase2/test_mock_runtime.py
.venv/bin/ruff format --check app/agent/runtime.py app/providers app/tools/knowledge.py tests/unit/phase2/test_external_adapters.py tests/unit/phase2/test_provider_factories.py tests/unit/phase2/test_runtime_events.py tests/integration/phase2/test_mock_runtime.py
git diff --check
```

## B7 — Test Responsibility And Brittleness Cleanup

**Goal:** Remove demonstrably duplicated or private-implementation assertions
while preserving every externally observable safety contract and test count
traceability.

**Allowed files:**

- `tests/unit/phase2/test_remediation_2.py`
- `tests/unit/phase2/test_external_adapters.py`
- `tests/unit/phase2/test_provider_factories.py`
- `tests/unit/phase2/test_task_registry.py`
- `tests/unit/phase2/test_events.py`
- `tests/integration/phase2/test_api_contract.py`
- `tests/integration/phase2/test_websocket_flow.py`

**Steps:**

- [ ] Build a duplicate/responsibility map before deleting any assertion.
- [ ] Remove only exact duplicate coverage or assertions tied solely to private
  attributes when an observable boundary test already exists.
- [ ] Do not delete Provider-family, terminal, isolation, containment,
  redaction or overflow assertions.
- [ ] Record removed/retained coverage in the node report.

**Acceptance:**

```bash
.venv/bin/python -m pytest tests/integration/phase2 tests/unit/phase2 -q
.venv/bin/ruff check tests/integration/phase2 tests/unit/phase2
.venv/bin/ruff format --check tests/integration/phase2 tests/unit/phase2
git diff --check
```

## B8 — Integrated Safety Acceptance And Canonical Evidence — Accepted

**Goal:** Independently accept the complete Phase 2B safety package and update
canonical status/evidence without changing product behavior.

**Allowed files:**

- `docs/phase-status.md`
- `docs/phases/phase-2-tutorial-parity.md`
- `docs/verification/phase-2-evidence.md`
- `docs/superpowers/plans/2026-08-07-phase-2b-safety-hardening.md`

**Steps:**

- [x] Run all backend and frontend regression gates from the accepted B1–B7
  working tree.
- [x] Confirm the Phase 2A browser evidence remains valid; rerun browser smoke
  only if B1–B7 changed a user-observable HTTP/WebSocket behavior.
- [x] Record actual HEAD/baseline, commands, exit codes, test totals and known
  limitations.
- [x] Codex independently reran the gates on 2026-08-07; results match B8.
- [x] Mark Phase 2B accepted after `.secrets.baseline` is refreshed and committed.
- [x] Start Phase 2C; do not create or move `v0.1-tutorial-parity` (pre-existing tag `50680e6`).

**B8 node record — 2026-08-07:** baseline `1d6166c`, actual HEAD `8dec2b7`
with the uncommitted B1–B7 worktree (per plan: no commits inside Reasonix).
Fresh gate results: E2E 1 passed; integration/unit 355 passed / 9 skipped;
frontend vitest 60 passed, eslint clean, build OK (identical bundle sizes to
2A); ruff check / ruff format clean; `git diff --check` clean. The first
pre-commit run refreshed
`.secrets.baseline` line-number refresh (fake-key entry in
`tests/unit/phase2/test_external_adapters.py` moved 23 → 39 after B6; no new
secrets). The refreshed baseline is included in the closeout commit.

**Codex independent acceptance run — 2026-08-07:** E2E 1 passed;
integration/unit 355 passed / 9 skipped; frontend vitest 60 passed, eslint and
build clean; ruff check / format and `git diff --check` clean. After staging
the generated baseline refresh, `pre-commit` passes all hooks. This confirms
B8 evidence and closes Phase 2B.

**Acceptance:**

```bash
.venv/bin/python -m pytest tests/e2e/phase2/test_tutorial_closure.py -q
.venv/bin/python -m pytest tests/integration/phase2 tests/unit/phase2 -q
pnpm --dir frontend exec vitest run
pnpm --dir frontend exec eslint src
pnpm --dir frontend run build
.venv/bin/ruff check app tests
.venv/bin/ruff format --check app tests
.venv/bin/pre-commit run --all-files
git diff --check
```

## Node Report Format

Every Reasonix node reports at most ten lines containing only:

- `CHANGED FILES`
- `RED`
- `GREEN`
- `STATIC CHECKS`
- `UNRESOLVED RISKS`

## Plan Self-Review

- B1/B2 own task lifecycle and exactly-one-terminal behavior.
- B3 owns live subscription, disconnect and overflow behavior.
- B4 owns HTTP validation, thread isolation and download containment.
- B5 owns parser/report atomicity and filesystem cleanup.
- B6 owns Provider/resource cleanup and sensitive-data redaction.
- B7 owns test responsibility without weakening contracts.
- B8 owns integrated evidence only.
- No node introduces a Phase 3-8 capability.
