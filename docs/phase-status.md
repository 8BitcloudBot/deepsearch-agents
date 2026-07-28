# Phase Status

## Current Phase

- **Phase:** 1 — DeepAgents Capability Examples
- **Status:** `awaiting_user_acceptance`
- **Started:** 2026-07-28
- **Target Tag:** `v0.0-deepagents-examples`（用户验收通过后创建）

## Phase 1-1 Task Progress

| Task | Name | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 0 | Establish Remediation State | completed | `adca654` | state established |
| 1 | Interrupt/Resume Behaviors | completed | `7762a13` | 6/6 behavioral tests pass |
| 2 | Real Backend/Store/Memory | completed | `e9a97b6` | 9/9 tests, real FilesystemBackend/InMemoryStore/MemoryMiddleware |
| 3 | Observable Middleware & Skills | completed | `fb66f5c` | 7/7 tests, wrap_model_call + SkillsMiddleware |
| 4 | Strengthen Import & Runner Tests | completed | `eeb3ca9` | 69→77 tests, strict assertions |
| 5 | Final Evidence & Gate | in_progress | — | — |

## Phase 1 Tasks (Completed)

| Task | Name | Status | Commit |
|------|------|--------|--------|
| 0 | Phase 0 Tag & Phase 1 State | completed | `a9b2f6a` |
| 1 | Lock Dependencies & API Surface | completed | `60b55a5` |
| 2 | Settings, Events, Runner | completed | `3d068b1` |
| 3 | Invoke, Stream, Chunks | completed | `187b99c` |
| 4 | Dictionary & Runnable Subagents | completed | `2180fce` |
| 5 | Interrupt, Approval, Resume | completed | `56b21e1` |
| 6 | Backend, Store, Memory | completed | `d411485` |
| 7 | Middleware & Skills | completed | `9e1d3da` |
| 8 | Integration Smoke & Final Gate | completed | `42320f3` |

## Blockers

None.

## Deviations

| # | Deviation | Reason |
|---|-----------|--------|
| 1 | SkillsMiddleware skills_metadata 需要完整 LangGraph runtime | 离线测试通过 source_labels 和目录验证 |
| 2 | 使用 `npx pnpm` 替代全局 `pnpm` | 无全局安装权限 |

## Next Steps

1. 用户验收通过后创建 `v0.0-deepagents-examples` tag
2. 用户明确授权后才编写 Phase 2 实施计划
