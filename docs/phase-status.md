# Phase Status

## Current Phase
- **Phase:** 2 — Tutorial Parity
- **Status:** `awaiting_independent_acceptance` — Phase 2-n6 complete
- **Target Tag:** `v0.1-tutorial-parity`（用户验收通过后创建）

## Tasks

| Task | Name | Commit | Notes |
|------|------|--------|-------|
| 0 | Freeze Contracts | `6a5d15a` | ADR 0003, deps locked |
| 1 | Settings/Events/Mocks | `c6af299` | 27 tests |
| 2 | Providers+Tools+SQL | `cba9315` | factory, tools, subagents, SQL policy |
| 2-n | Phase 2 remediation | various | event contracts, strict JSON, evidence |
| 3-4 | Workspace & Agent | REJECTED → REMEDIATED | 8 items fixed |
| **2-n4** | **Phase 2-n4 Remediation** | **see below** | **6 commits, symlink exploit fixed** |
| 5 | FastAPI/WebSocket | **blocked** | — |
| 6 | React Workbench | **blocked** | — |
| 7 | Document & Verify | **blocked** | — |

### Phase 2-n4 Commits
| # | Commit | Message |
|---|--------|---------|
| 0 | `65434f3` | docs: record phase two task three four rejection |
| 1 | `c9f192a` | fix: secure workspace atomic file replacement |
| 2 | `3665f32` | fix: route runtime uploads through safe reader |
| 3 | `8e58430` | fix: enforce tutorial runtime event ownership |
| 4 | `7ea359f` | fix: restore tutorial factory and model configuration |
| 5 | `cb1175c` | fix: bound workbook reads and render report tables |

## Tests
- Total: 309 passed, 11 skipped
- Pre-commit: ruff ✅, ruff-format ✅, detect-secrets ✅
- No v0.1 tags exist

## Blockers

- Task 3: fixed .tmp symlink allows overwriting files outside workspace
- Task 4: factory missing workspace_factory; mock runtime tool events out of order; real runtime duplicates tool events; real-model smoke discards API key
- Task 5 not authorized

## Tests
- Unit: 302 passed
- Integration: 8 skipped (no model key), 2 skipped (smoke — no external config)
- MySQL: 6 passed (PHASE2_MYSQL_INTEGRATION=1)
