# Phase Status

## Current Phase
- **Phase:** 2 — Tutorial Parity
- **Status:** `remediation_in_progress` — Tasks 3-4 rejected
- **Target Tag:** `v0.1-tutorial-parity`（用户验收通过后创建）

## Tasks

| Task | Name | Commit | Notes |
|------|------|--------|-------|
| 0 | Freeze Contracts | `6a5d15a` | ADR 0003, deps locked |
| 1 | Settings/Events/Mocks | `c6af299` | 27 tests |
| 2 | Providers+Tools+SQL | `cba9315` | factory, tools, subagents, SQL policy |
| 2-n | Phase 2 remediation | various | event contracts, strict JSON, evidence |
| 3 | Workspace & Reports | REJECTED | symlink exploit, 8 items failed |
| 4 | Agent & Runtimes | REJECTED | event ownership, factory contract, smoke gaps |
| 3-4-r | Phase 2-n4 Remediation | in progress | Tasks 0-6 pending |
| 5 | FastAPI/WebSocket | **blocked** | — |
| 6 | React Workbench | **blocked** | — |
| 7 | Document & Verify | **blocked** | — |

## Blockers

- Task 3: fixed .tmp symlink allows overwriting files outside workspace
- Task 4: factory missing workspace_factory; mock runtime tool events out of order; real runtime duplicates tool events; real-model smoke discards API key
- Task 5 not authorized

## Tests
- Unit: 302 passed
- Integration: 8 skipped (no model key), 2 skipped (smoke — no external config)
- MySQL: 6 passed (PHASE2_MYSQL_INTEGRATION=1)
