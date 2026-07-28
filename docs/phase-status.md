# Phase Status

> 项目阶段状态追踪。更新时机：每个 Task 开始前和完成后。

## Current Phase

- **Phase:** 1 — DeepAgents Capability Examples
- **Status:** `awaiting_user_acceptance`
- **Started:** 2026-07-28
- **Target Tag:** `v0.0-deepagents-examples`（用户验收通过后创建）

## Phase 1 Task Progress

| Task | Name | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 0 | Phase 0 Tag & Phase 1 State | completed | `a9b2f6a` | v0.0-foundation verified |
| 1 | Lock Dependencies & API Surface | completed | `60b55a5` | v0.6.12/lg1.2.9/lc1.5.1, ADR created |
| 2 | Settings, Events, Runner | completed | `3d068b1` | 35 tests pass |
| 3 | Invoke, Stream, Chunks | completed | `187b99c` | 37 tests pass |
| 4 | Dictionary & Runnable Subagents | completed | `2180fce` | 42 tests pass |
| 5 | Interrupt, Approval, Resume | completed | `56b21e1` | 42 tests pass |
| 6 | Backend, Store, Memory | completed | `d411485` | 42 tests pass |
| 7 | Middleware & Skills | completed | `9e1d3da` | 42 tests pass, SKILL.md created |
| 8 | Integration Smoke & Final Gate | in_progress | — | — |

## Blockers

None.

## Deviations

| # | Deviation | Reason |
|---|-----------|--------|
| 1 | 使用 `npx pnpm` 替代全局 `pnpm` | 无全局安装权限 |
| 2 | Node 22 通过 standalone binary 验证 | nvm 未安装于本机 |

## Next Steps

1. 完成 Task 8 最终门禁
2. 用户验收通过后创建 `v0.0-deepagents-examples` tag
3. 用户授权后开始 Phase 2
