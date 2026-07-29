# Phase Status

## Current Phase
- **Phase:** 2 — Tutorial Parity
- **Status:** `awaiting_task_3_acceptance`
- **Target Tag:** `v0.1-tutorial-parity`（用户验收通过后创建）

## Tasks

| Task | Name | Commit | Notes |
|------|------|--------|-------|
| 0 | Freeze Contracts | `6a5d15a` | ADR 0003, deps locked |
| 1 | Settings/Events/Mocks | `c6af299` | 27 tests |
| 2 | Providers+Tools+SQL | `cba9315` | factory, tools, subagents, SQL policy |
| 2-n | Phase 2 remediation | various | event contracts, strict JSON, evidence |
| **3-r** | **Task 3 Remediation** | **`87a4373`, `e74c64a`** | **UnsafeWorkspacePath, real format parsers, macro/ZIP bomb defense, untrusted delimiters, session-based reports, 91 tests** |
| 4 | Agent & Runtimes | `c5b579e` | factory, mock/deepagents runtimes, 24 tests |
| 5 | FastAPI/WebSocket | pending | — |
| 6 | React Workbench | pending | — |
| 7 | Document & Verify | pending | — |

## Blockers

None.

## Tests
- Unit: 302 passed
- Integration: 8 skipped (no model key), 2 skipped (smoke — no external config)
- MySQL: 6 passed (PHASE2_MYSQL_INTEGRATION=1)

## JsonValue Contract
- PEP 695 `type` recursive alias; `field_validator(mode="before")` rejects non-JSON before coercion
- JSON Schema contains `$defs/JsonValue`