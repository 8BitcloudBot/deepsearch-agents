# Phase Status

## Current Phase
- **Phase:** 2 — Tutorial Parity
- **Status:** `awaiting_user_acceptance`
- **Target Tag:** `v0.1-tutorial-parity`（用户验收通过后创建）

## Phase 2-n2 Tasks

| Task | Name | Commit | Notes |
|------|------|--------|-------|
| 1 | Recursive Event Type | `6e79fa6` | JsonValue annotations, model_validator |
| 2 | Delete False-Green Tests | `5df1ac5` | removed pass/placeholder, added provider SQL limit test |
| 3 | Exact Subagent Contracts | `08630a4` | 10 tests: names, prompts, tools, domain isolation |
| 4 | Remove Any Exposure + Evidence | `3e614ec` / `7ab3186` | model_validator, evidence reconciled |

## Blockers

**None.** Task 3 remains blocked until full Phase 2 user acceptance.

## Tests
- Unit: 167 passed
- Integration: 8 skipped (no model key), 2 skipped (no external config)
- MySQL: 6 passed (PHASE2_MYSQL_INTEGRATION=1)

## Known Limitations
- Pydantic 2.13 不支持递归类型；`TutorialEvent.data` 字段类型为 `dict[str, Any]`，由 `model_validator` 在构造时执行 `_validate_json_value`
- `InMemoryEventBus.emit` 参数类型为 `dict[str, "JsonValue"] | None`
- 前向引用 `"JsonValue"` 在 Pydantic 模型中引发递归；`Any` + 运行时验证是当前版本的最优方案
