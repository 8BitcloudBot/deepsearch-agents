# Phase Status

## Current Phase
- **Phase:** 2 — Tutorial Parity
- **Status:** `awaiting_user_acceptance`
- **Target Tag:** `v0.1-tutorial-parity`（用户验收通过后创建）

## Tasks

| Task | Name | Commit | Notes |
|------|------|--------|-------|
| 0 | Freeze Contracts | `6a5d15a` | ADR 0003, deps locked |
| 1 | Settings/Events/Mocks | `c6af299` | 27 tests |
| 2 | Providers+Tools+SQL | `cba9315` | factory, tools, subagents, SQL policy |
| 2-n | Phase 2 remediation | various | event contracts, strict JSON, evidence |
| **3** | **Workspace & Reports** | **`397d9bb`** | **SessionWorkspace, ContextVar, file readers, Markdown/PDF, 27 tests** |
| 4 | Agent & Runtimes | pending | — |
| 5 | FastAPI/WebSocket | pending | — |
| 6 | React Workbench | pending | — |
| 7 | Document & Verify | pending | — |

## Blockers

None.

## Tests
- Unit: 214 passed
- Integration: 8 skipped (no model key), 2 skipped (no external config)
- MySQL: 6 passed (PHASE2_MYSQL_INTEGRATION=1)

## JsonValue Contract
- PEP 695 `type` recursive alias; `field_validator(mode="before")` rejects non-JSON before coercion
- JSON Schema contains `$defs/JsonValue`