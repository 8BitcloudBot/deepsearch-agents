# Phase 2A React Workbench Implementation Plan

**Execution status:** Completed and accepted on 2026-08-07. The unchecked
step boxes below are preserved as the original execution plan, not as current
outstanding work. Current status and evidence live in
[`../../phase-status.md`](../../phase-status.md) and
[`../../verification/phase-2-evidence.md`](../../verification/phase-2-evidence.md).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Phase 0 React placeholder with a small responsive research workbench that exposes the accepted Phase 2A backend journey from thread creation through reports and terminal state.

**Architecture:** Keep one page and the existing React/Vite/Vitest stack. Put backend contracts and transport helpers in focused TypeScript modules, keep session state in one hook, and render the header, controls, timeline, status and artifact panel from that state. Use the browser WebSocket and `fetch` directly; do not add a component framework, state library or Markdown-to-HTML renderer.

**Tech Stack:** React 18, TypeScript, Vite, Vitest, Testing Library, native `fetch`, native `WebSocket`, CSS.

## Global Constraints

- Backend endpoints remain exactly `/health`, `/api/upload`, `/api/task`, `/api/task/{thread_id}/cancel`, `/api/files`, `/api/download`, and `/ws/{thread_id}`.
- One client-created UUID is reused for upload, WebSocket, task, cancel, file list and download.
- Events are live-only and deduplicated by `(thread_id, sequence)`; no replay or recovery is added.
- The timeline renders every allowed task, agent, tool, artifact and terminal event in sequence order, including `data` as safe text.
- Start requires an uploaded constraint file and a non-empty query; cancel is available only for an active task.
- Terminal state is accepted once and cannot be changed by later events.
- Markdown is previewed as plain text; never use `dangerouslySetInnerHTML`.
- Provider keys, raw exception representations, absolute paths and raw provider responses never enter browser state.
- Layout must work at 1440px and 375px without horizontal page scrolling; focus styles and reduced-motion behavior are required.
- No backend edits, API renames, persistence, reconnect replay, authentication, new runtime dependencies, commit, tag or push.

---

### Task 1: Define typed contracts and transport helpers (F1)

**Files:**
- Create: `frontend/src/workbench/types.ts`
- Create: `frontend/src/workbench/api.ts`
- Test: `frontend/src/App.test.tsx`

**Interfaces:**
- `TutorialEvent` has `version`, `sequence`, `thread_id`, `type`, `message`, `data`, `timestamp`.
- `RunStatus` is `"idle" | "uploading" | "ready" | "running" | "success" | "failed" | "cancelled" | "connection-error"`.
- `health(baseUrl)` returns provider/runtime mode strings from `GET /health`.
- `uploadConstraint(baseUrl, threadId, file)` posts `FormData` to `/api/upload` and returns the JSON upload response.
- `startTask(baseUrl, threadId, query)` posts `{query, thread_id}` to `/api/task`.
- `cancelTask(baseUrl, threadId)` posts to `/api/task/{threadId}/cancel`.
- `listFiles(baseUrl, threadId)` gets `/api/files?thread_id=...`.
- `downloadUrl(baseUrl, threadId, path)` returns a URL using only the server-returned relative `path` and current thread ID.
- `parseEvent(raw)` validates JSON shape, version `1`, UUID/thread fields, integer positive sequence and an allowed event type; invalid input throws a user-safe `Error` without including raw payload text.

- [ ] **Step 1: Write failing contract tests**

Add tests for `parseEvent` accepting a valid event, rejecting unknown version/malformed JSON, and `downloadUrl` preserving a relative artifact path without exposing a filesystem path.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `pnpm --dir frontend exec vitest run src/App.test.tsx -t "contract"`

Expected: FAIL because `types.ts`, `api.ts`, and the named helpers do not exist.

- [ ] **Step 3: Implement the minimal typed helpers**

Use `encodeURIComponent` for query parameters, `FormData` for upload, and a shared `requestJson` helper that throws `HTTP <status>: <detail>` while discarding response internals. Keep `downloadUrl` limited to the API base, current UUID and the server-returned relative path.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `pnpm --dir frontend exec vitest run src/App.test.tsx -t "contract"`

Expected: all contract tests pass.

### Task 2: Build thread/session state and the static responsive shell (F1)

**Files:**
- Create: `frontend/src/workbench/useWorkbench.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/app.css`
- Test: `frontend/src/App.test.tsx`

**Interfaces:**
- `useWorkbench()` owns `threadId`, health modes, selected file, uploaded file, query, status, error, events, terminal event, files, markdown and connection state.
- The hook exposes `newSession()`, `connect()`, `selectFile(file)`, `upload()`, `submit()`, `cancel()`, and `refreshArtifacts()`.
- `App` renders `SessionHeader`, `TaskComposer`, `RunStatus`, `EventTimeline`, and `ArtifactPanel` in one page without a router.

- [ ] **Step 1: Write failing shell/state tests**

Add tests that render the heading, a UUID thread label, provider/runtime health labels, disabled start control before upload/query, and `newSession()` clearing query, file, timeline, terminal and artifacts.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `pnpm --dir frontend exec vitest run src/App.test.tsx -t "session|shell"`

Expected: FAIL because the placeholder app has no workbench controls or session hook.

- [ ] **Step 3: Implement the shell and state skeleton**

Create the UUID once per session with `crypto.randomUUID()`, load `/health` on mount, connect the WebSocket for the active thread before any task submission, and expose only the state/actions required by the components. Reset closes the old socket before replacing the UUID and clears all run state.

- [ ] **Step 4: Add responsive CSS and accessibility**

Use the research-console palette from the approved design, a single-column layout, `@media (min-width: 960px)` spacing adjustments, `@media (prefers-reduced-motion: reduce)` to disable transitions, visible `:focus-visible` outlines, and no fixed-width children that cause overflow at 375px.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run: `pnpm --dir frontend exec vitest run src/App.test.tsx -t "session|shell"`

Expected: all shell/state tests pass.

### Task 3: Implement upload, query, cancellation and live event timeline (F2/F3)

**Files:**
- Modify: `frontend/src/workbench/useWorkbench.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/app.css`
- Test: `frontend/src/App.test.tsx`

**Interfaces:**
- `WebSocket` is opened at `/ws/{threadId}` before `startTask` is called; `ping` messages are ignored by the timeline and `pong` is not rendered.
- Parsed events are deduplicated by `${thread_id}:${sequence}`, sorted numerically by sequence, and appended immutably.
- `task_started` sets `running`; `task_completed`, `task_failed`, and `task_cancelled` set the terminal status exactly once.
- WebSocket `close` sets `connection-error` only when no terminal event has been accepted; close code `1013` uses the stable message `Event stream interrupted because the consumer was too slow.`.

- [ ] **Step 1: Write failing behavior tests**

Add tests for successful upload enabling start, upload rejection showing status context, task POST using the same UUID, a fake WebSocket delivering out-of-order duplicate events, all three terminal mappings, cancel using the active UUID, and close code `1013` showing a stream interruption without changing a completed run.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `pnpm --dir frontend exec vitest run src/App.test.tsx -t "upload|task|event|cancel|WebSocket"`

Expected: FAIL because the placeholder has no transport state or timeline.

- [ ] **Step 3: Implement minimal event-driven state transitions**

Keep the accepted terminal event in a ref/state guard so later events remain visible but cannot change `success`, `failed` or `cancelled`. Surface API errors as `HTTP <status>: <detail>` and never store response bodies that are not the stable detail field.

- [ ] **Step 4: Render the complete timeline**

For every event render sequence, local time, type, message and a collapsed-safe `<pre>` JSON representation of `data`; never omit task, agent, tool or artifact events. Render status labels separately from the raw event text.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run: `pnpm --dir frontend exec vitest run src/App.test.tsx -t "upload|task|event|cancel|WebSocket"`

Expected: all F2/F3 behavior tests pass.

### Task 4: Add artifact listing, safe Markdown preview and downloads (F4)

**Files:**
- Modify: `frontend/src/workbench/useWorkbench.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/app.css`
- Test: `frontend/src/App.test.tsx`

**Interfaces:**
- On `task_completed`, call `listFiles(baseUrl, threadId)` and fetch Markdown through the same current-thread `downloadUrl` for plain-text preview.
- Display only files returned for the active thread; identify `tutorial-report.md` and `tutorial-report.pdf` by server-returned `name/path`.
- Markdown and PDF controls use normal anchors with `download` and the generated API URL; no arbitrary path input is accepted.
- A new run, failed run, cancelled run or new session clears the previous preview and artifact list before work begins.

- [ ] **Step 1: Write failing artifact tests**

Add tests for successful completion refreshing files, Markdown text appearing in a `<pre>`, both download links using the current UUID and relative server path, missing Markdown showing a stable empty state, and stale success data disappearing when a new run starts or fails.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `pnpm --dir frontend exec vitest run src/App.test.tsx -t "artifact|Markdown|download|stale"`

Expected: FAIL because the placeholder has no artifact panel or post-terminal refresh.

- [ ] **Step 3: Implement artifact refresh and plain-text preview**

Fetch only after `task_completed`, accept only the two expected report names for the panel, and render Markdown with `<pre>` text content. Use stable empty/error messages when files are missing or the preview fetch fails.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `pnpm --dir frontend exec vitest run src/App.test.tsx -t "artifact|Markdown|download|stale"`

Expected: all artifact tests pass.

### Task 5: Integrated frontend evidence and documentation (F5)

**Files:**
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/app.css`
- Modify: `docs/phase-status.md`
- Modify: `docs/verification/phase-2-evidence.md`
- Modify: `README.md` only if the existing quick-start section lacks the frontend command required by the addendum

**Interfaces:**
- The final app exposes the full frozen backend contract without changing backend files.
- Frontend scripts remain `pnpm --dir frontend exec vitest run`, `pnpm --dir frontend exec eslint src`, and `pnpm --dir frontend run build`.

- [ ] **Step 1: Add integrated interaction tests**

Cover the complete sequence create thread → connect → upload → submit → provider events → terminal → files/preview/download, plus failure, cancellation, disconnect and reset paths using deterministic `fetch` and WebSocket test doubles.

- [ ] **Step 2: Run the complete frontend test suite**

Run: `pnpm --dir frontend exec vitest run`

Expected: all frontend tests pass with no unhandled errors.

- [ ] **Step 3: Run frontend lint and production build**

Run: `pnpm --dir frontend exec eslint src` and `pnpm --dir frontend run build`

Expected: both exit 0 and `frontend/dist` is generated without TypeScript errors.

- [ ] **Step 4: Run backend regression gates**

Run: `.venv/bin/python -m pytest tests/e2e/phase2/test_tutorial_closure.py -q`, `.venv/bin/python -m pytest tests/integration/phase2 tests/unit/phase2 -q`, `.venv/bin/ruff check app tests`, `.venv/bin/ruff format --check app tests`, `.venv/bin/pre-commit run --all-files`, and `git diff --check`.

Expected: all commands exit 0; no backend assertions are removed or weakened.

- [ ] **Step 5: Run desktop/mobile browser smoke**

Start the documented local mock backend and frontend only if the repository quick start already provides those commands. Exercise upload, task start, live events, terminal state, Markdown preview and both download links at 1440px and 375px. Record command, viewport and result in `docs/verification/phase-2-evidence.md`; if browser automation is unavailable, record the exact unrun smoke as unresolved rather than claiming it passed.

- [ ] **Step 6: Synchronize canonical status/evidence**

Record the actual final commit, frontend test/lint/build counts, browser smoke result, and that React Workbench is now implemented. Keep Phase 2B pending until its safety-hardening work is explicitly run; do not create `v0.1-tutorial-parity`.

## Plan Self-Review

- Scope coverage: F1–F5 map to the addendum's five vertical slices; deferred persistence, replay, authentication, governance and future API migration have no task.
- Placeholder scan: no unfinished placeholder markers or unspecified “handle edge cases” steps remain; each code change names a file, behavior, test command and expected result.
- Type consistency: `TutorialEvent`, `RunStatus`, `downloadUrl`, transport helpers and `useWorkbench` state are defined before the components and tests that consume them.
- Safety review: upload and task use one UUID, WebSocket connects before submission, terminal state is guarded once, Markdown is plain text, and server-returned relative paths are the only download inputs.
