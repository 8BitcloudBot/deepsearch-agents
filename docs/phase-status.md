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
| 4 | Remove Any Exposure + Evidence | `c252de0` / `92a28d2` / `b7eadda` | PEP695 type, field_validator(mode="before"), strict rejection |

## Blockers

**None.** Task 3 remains blocked until full Phase 2 user acceptance.

## Tests
- Unit: 185 passed
- Integration: 8 skipped (no model key), 2 skipped (no external config)
- MySQL: 6 passed (PHASE2_MYSQL_INTEGRATION=1)

## JsonValue Contract
- PEP 695 `type` recursive alias: `None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]`
- `@field_validator("data", mode="before")` rejects bytes/set/tuple/object/non-str keys before Pydantic coercion
- JSON Schema contains `$defs/JsonValue`
