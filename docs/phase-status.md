# Phase Status

## Current Phase
- **Phase:** 2 — Tutorial Parity
- **Status:** `awaiting_independent_acceptance` — Phase 2-n6 remediated
- **Target Tag:** `v0.1-tutorial-parity`（用户验收通过后创建）

## Tasks

| Task | Name | Commit | Notes |
|------|------|--------|-------|
| 0 | Freeze Contracts | `6a5d15a` | ADR 0003, deps locked |
| 1 | Settings/Events/Mocks | `c6af299` | 27 tests |
| 2 | Providers+Tools+SQL | `cba9315` | factory, tools, subagents, SQL policy |
| 3-4 | Workspace & Agent | remediated | n4/n5/n6 fixes applied |
| 5 | FastAPI/WebSocket | **blocked** | — |
| 6 | React Workbench | **blocked** | — |
| 7 | Document & Verify | **blocked** | — |

### Remediation Commits (post-40b91b0)

| Commit | Message |
|--------|---------|
| `65434f3` | docs: record phase two task three four rejection |
| `c9f192a` | fix: secure workspace atomic file replacement |
| `3665f32` | fix: route runtime uploads through safe reader |
| `8e58430` | fix: enforce tutorial runtime event ownership |
| `7ea359f` | fix: restore tutorial factory and model configuration |
| `cb1175c` | fix: bound workbook reads and render report tables |
| `05d67fb` | docs: reconcile phase two task three four evidence |
| `51d2b89` | fix: validate upload content by target extension not tmp suffix |
| `2241ef2` | fix: enforce wrapper failure contract and fix artifact dedup |

## Tests
- Total: 318 passed, 11 skipped
- Pre-commit: ruff ✅, ruff-format ✅, detect-secrets ✅
- No v0.1 tags exist
