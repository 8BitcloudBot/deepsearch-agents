# Phase 2 Handoff — Phase 2-n4 Remediation

**Created:** 2026-07-29
**Updated for:** Phase 2-n4 Tasks 3-4 remediation
**For:** Next agent session continuing from `40b91b0` (or later)

## Continuation Goal

Complete Phase 2-n4 Tasks 0-6 remediation. See full plan at:
`docs/superpowers/plans/Phase 2-n4.md`

## Current State

- **HEAD:** `bc41e3c` — Phase 2-n6 acceptance gate
- **Tests:** 322 passed / 11 skipped
- **Tags:** `v0.0-foundation`, `v0.0-deepagents-examples`
- **Phase 2 Tasks 1-2:** ✅ Complete and accepted
- **Phase 2 Tasks 3-4:** remediated (n4/n5/n6 fixes applied, awaiting acceptance)
- **Task 5:** 🚫 Blocked — not authorized

## Key Artifacts (new since b30cbc3)

| Path | Role |
|------|------|
| `docs/superpowers/plans/Phase 2-n4.md` | Current remediation plan |
| `app/agent/factory.py` | `create_tutorial_agent` — needs workspace_factory |
| `app/agent/runtime.py` | `MockTutorialRuntime` + `DeepAgentsTutorialRuntime` |
| `app/tools/files.py` | `UnsafeWorkspacePath`, pypdf/docx/openpyxl readers |
| `app/tools/reports.py` | session_context-based reports, STSong-Light |
| `tests/unit/phase2/test_agent_factory.py` | 9 tests |
| `tests/unit/phase2/test_runtime_events.py` | 10 tests |
| `tests/unit/phase2/test_workspace.py` | 28 tests |
| `tests/unit/phase2/test_file_reader.py` | 38 tests |
| `tests/unit/phase2/test_reports.py` | 16 tests |
| `tests/integration/phase2/test_mock_runtime.py` | 2 tests |
| `tests/integration/phase2/test_real_model_smoke.py` | 1 gated test |

## Rejection Items

1. **symlink exploit:** `save_uploaded_file` uses fixed `.name.tmp` — pre-created symlink allows overwriting files outside workspace
2. **reader bypass:** factory/runtime bypass `read_uploaded_file`, calling `Path.read_text` directly
3. **event ordering:** Mock runtime uses `_emit_tool_pair` — both events fire before provider call
4. **duplicate events:** Real runtime stream normalizer duplicates tool events already sent by wrappers
5. **missing agent_name:** agent_started/agent_completed don't carry agent_name in data
6. **factory signature:** missing `workspace_factory` parameter
7. **smoke config gaps:** MODEL_API_KEY/MODEL_BASE_URL read but not used for actual model construction
8. **XLSX unbounded:** `list(ws.iter_rows())` materializes entire worksheet

## Next Steps

1. Execute Phase 2-n4.md Tasks 0-6 in order
2. Each task: RED → GREEN → commit (exact messages in the plan)
3. Do NOT start Task 5
4. Do NOT create `v0.1-tutorial-parity`
