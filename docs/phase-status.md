# Phase Status

## Current Phase

- **Phase:** 2 — Tutorial Parity
- **Status:** `in_progress`
- **Started:** 2026-07-29
- **Target Tag:** `v0.1-tutorial-parity`（用户验收通过后创建）

## Phase 2 Task Progress

| Task | Name | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 0 | Freeze Contracts & Start Evidence | completed | `6a5d15a` | ADR 0003, all deps locked |
| 1 | Settings, Events, Mock Adapters | completed | `c6af299` | 27 tests pass |
| 2 | Web/MySQL/RAGFlow Providers | completed | `cba9315` | factory, tools, subagents, SQL policy |
| 2-R | Provider Contract RED Tests | completed | `624464e` | 6 test files, 9 RED failures |
| 2-F | Provider Contract Fixes | completed | `bd38a60` | factory, RAGFlow 0.26.0, SQL validation, mysql bootstrap |
| 3 | Workspace & Report Delivery | pending | — | — |
| 4 | Main Agent & Both Runtimes | pending | — | — |
| 5 | FastAPI, WebSocket, Upload, Cancel | pending | — | — |
| 6 | React Tutorial Workbench | pending | — | — |
| 7 | Document, Verify, Stop | pending | — | — |

## Blockers

None.

## Deviations

| # | Deviation | Reason |
|---|-----------|--------|
| 1 | Tests use inline `# pragma: allowlist secret` for fake keys | detect-secrets false positives |
| 2 | RAGFlow `Session.ask(stream=False)` may return str or dict | 0.26.0 API; handled in adapter |

## MySQL Bootstrap

- Container: `deepsearch-agents-mysql-1` on port 3307
- `tutorial_reader` account: SELECT only on `research_copilot.*`
- INSERT rejected at DB level; row count unchanged (3 rows)
- Integration tests: 6 passed (PHASE2_MYSQL_INTEGRATION=1)

## External Smoke

- Tavily: skipped (PHASE2_TAVILY_SMOKE not set)
- RAGFlow: skipped (PHASE2_RAGFLOW_SMOKE not set)
