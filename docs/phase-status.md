# Phase Status

## Current Phase
- **Phase:** 2 — Tutorial Parity
- **Status:** `awaiting_independent_acceptance`
- **Target Tag:** `v0.1-tutorial-parity`（用户验收通过后创建）
- **Acceptance Base:** `bc41e3c` (Phase 2 remediation baseline; current HEAD may differ)

## Tasks

| Task | Name | Status |
|------|------|--------|
| 0 | Freeze Contracts | ✅ accepted |
| 1 | Settings/Events/Mocks | ✅ accepted |
| 2 | Providers+Tools+SQL | ✅ accepted |
| 3-4 | Workspace & Agent | remediated (awaiting acceptance) |
| 5 | FastAPI/WebSocket | 🚫 blocked |
| 6 | React Workbench | 🚫 blocked |
| 7 | Document & Verify | 🚫 blocked |

### Historical Rejections (archived)

> Tasks 3-4 were independently rejected for: fixed .tmp symlink exploit,
> content validation bypass via temp suffix, duplicate tool events,
> exception swallowing in mock runtime, artifact dedup mismatch,
> missing workspace_factory, and discarded MODEL_API_KEY.
> All items fixed across Phases 2-n4 through 2-n6. See commit log for details.

## Tests
- Total: 322 passed, 11 skipped
- Pre-commit: ruff ✅, ruff-format ✅, detect-secrets ✅
- No v0.1 tags exist
