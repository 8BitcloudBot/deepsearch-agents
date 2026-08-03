# Phase 2A Handoff - WebSocket E2E to React Workbench

**Created:** 2026-08-01
**Repository:** `deepsearch-agents`
**HEAD at handoff:** `537cc2e` (`test: e2e closure with unique marker and provider coverage`)

## Continuation Goal

Close the one remaining automated acceptance gap in the Phase 2A backend
closure: prove the complete user path through `/ws/{thread_id}`. Then accept
the backend slice and authorize A1 / Task 6 React Workbench. Do not begin
Phase 2B, Phase 2C, Phase 3, or create a `v0.1*` tag.

## Current State

- Phase 0 and Phase 1 are accepted.
- Phase 2 Tasks 0-4 are accepted.
- Task 5 implementation is present. The latest test-only commits are:
  - `ef58685` - HTTP/event-bus E2E closure.
  - `537cc2e` - adds `tmp_path` isolation and an exact unique upload marker.
- `537cc2e` passes all current offline gates, but its E2E test still directly
  subscribes to `InMemoryEventBus` and collects `subscription.queue` instead
  of connecting `/ws/{thread_id}`. It is therefore not the required real
  WebSocket E2E regression test.
- Independent manual smoke did prove the implementation works through:
  `POST /api/upload -> WebSocket connect -> POST /api/task -> events through
  WebSocket -> task_completed -> list/download Markdown/PDF`. It observed all
  three provider categories, exactly one terminal, the unique constraint in
  Markdown, provider modes, and a `%PDF` PDF. This was run in a temporary
  directory and produced no repository artifacts.

## Durable Decisions

- Demo-first remains the priority: a credible Phase 2A backend vertical slice
  precedes the React Workbench; broad production hardening belongs in Phase 2B.
- Do not accept an internal EventBus subscription as a substitute for a
  WebSocket user-flow E2E test.
- Keep critical safety blocking: thread/file isolation, containment, upload
  safety, redaction, and exactly one terminal event.
- After the narrowly scoped E2E repair is independently verified, proceed
  directly to A1 / Task 6 React Workbench. Do not reopen or refactor backend
  implementation without an observed defect.

## Key Artifacts

- Current phase status: `docs/phase-status.md`
- Phase 2 scope and exit criteria: `docs/phases/phase-2-tutorial-parity.md`
- Original Task 5 acceptance contract: `docs/superpowers/plans/2026-07-29-agent-engineering-research-copilot-phase-2-plan.md` (Task 5, Step 1)
- Prior Tasks 3-4 independent-acceptance handoff: `docs/handoffs/2026-07-29-phase2-n6-independent-acceptance-handoff.md`
- Current E2E target: `tests/e2e/phase2/test_tutorial_closure.py`
- WebSocket implementation and focused tests: `app/api/server.py`, `tests/integration/phase2/test_websocket_flow.py`

## Latest Verification

Run at `537cc2e`:

```text
.venv/bin/python -m pytest tests/ -q
348 passed, 11 skipped, 1 warning

.venv/bin/ruff check app examples tests scripts
.venv/bin/ruff format --check app examples tests scripts
.venv/bin/pre-commit run --all-files
docker compose config
git diff --check
all passed

git tag --list 'v0.1*'
no output
```

Focused E2E plus Task 5 test set also passed: `1 passed` and `26 passed`.
The one warning is Starlette's deprecation warning for `TestClient` with the
installed `httpx` version; it is pre-existing and non-blocking for this scope.

## Working Tree Warning

The worktree is intentionally dirty with a user-approved documentation
reorganization: modified `README.md`, `docs/phase-status.md`, historical
plans/handoffs/evidence, plus untracked `docs/README.md`, `docs/roadmap.md`,
`docs/phases/`, `docs/archive/`, and documentation indexes. Preserve all of
these changes. They are not part of DeepSeek's E2E repair. Do not run a broad
format, reset, checkout, clean, or stage-all operation.

This handoff file is itself untracked until the documentation reorganization
is intentionally committed.

## Required Remediation

Replace the current E2E's event-bus path with a fully product-facing test:

1. Use isolated `tmp_path` roots and a unique thread UUID.
2. Use one synchronous `TestClient` context; do not use `pytest.mark.asyncio`,
   `AsyncClient`, `ASGITransport`, `events.subscribe`, or `subscription.queue`.
3. Upload a uniquely marked `constraints.md` through `/api/upload`.
4. Open `/ws/{thread_id}` and complete the subscription before posting
   `/api/task`.
5. Receive events only with `ws.receive_*` until a terminal event. Assert all
   three provider tool names and exactly one `task_completed`.
6. List and download both reports through HTTP. Assert the complete unique
   marker and all three provider modes in Markdown, plus `%PDF` for PDF.
7. Stage only the E2E test for the repair commit; do not touch the dirty docs.

The independent manual smoke already demonstrated that this sync TestClient
arrangement works with the current server.

## Next Steps

1. Inspect `git status --short`, `git log --oneline ef58685..HEAD`, and the
   E2E diff before accepting any new DeepSeek claim.
2. Require the bounded E2E repair above; reject a repeat that still uses the
   EventBus as the observable path.
3. Rerun the focused E2E, Task 5 suite, full test suite, lint/format,
   pre-commit, Compose, and diff checks.
4. On success, explicitly accept the Phase 2A backend slice and authorize A1
   / Task 6 React Workbench. Do not implement React in the acceptance session
   unless the user asks.
5. For React work, follow `docs/phases/phase-2-tutorial-parity.md`: single
   workbench, WebSocket-driven events, upload, task status/cancel, Markdown
   preview, artifact downloads, Vitest plus desktop/mobile browser smoke.

## Suggested Skills

- `using-superpowers`: mandatory skill discovery at session start.
- `two-axis-review`: separate repository-quality findings from Phase 2A
  contract compliance when reviewing the E2E repair.
- `verification-before-completion`: require fresh commands before acceptance.
- `brainstorming`: before beginning A1 React work, to confirm the workbench's
  interaction and visual requirements without expanding scope.
