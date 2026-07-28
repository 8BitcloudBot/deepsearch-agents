# Phase Status

> 项目阶段状态追踪。更新时机：每个 Task 开始前和完成后。

## Current Phase

- **Phase:** 1 — DeepAgents Capability Examples
- **Status:** `in_progress`
- **Started:** 2026-07-28
- **Target Tag:** `v0.0-deepagents-examples`（用户验收通过后创建）

## Phase 1 Task Progress

| Task | Name | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 0 | Phase 0 Tag & Phase 1 State | completed | `a9b2f6a` | v0.0-foundation verified |
| 1 | Lock Dependencies & API Surface | completed | `60b55a5` | v0.6.12/lg1.2.9/lc1.5.1, ADR created |
| 2 | Settings, Events, Runner | completed | `3d068b1` | 35 tests pass, events/runner/settings |
| 3 | Invoke, Stream, Chunks | in_progress | — | — |
| 4 | Dictionary & Runnable Subagents | pending | — | — |
| 5 | Interrupt, Approval, Resume | pending | — | — |
| 6 | Backend, Store, Memory | pending | — | — |
| 7 | Middleware & Skills | pending | — | — |
| 8 | Integration Smoke & Final Gate | pending | — | — |

## Completed Phases

- **Phase 0:** Foundation — `v0.0-foundation` (tag: `9715255`)
- **Phase 0-1:** Acceptance Blocker Remediation
- **Phase 0-2:** Final Acceptance Consistency

## Blockers

| # | Blocker | Status |
|---|---------|--------|
| 1 | DeepAgents/LangGraph dependency and API surface not yet locked | pending |

## Deviations

None yet.

## Next Steps

1. Complete Task 0: establish Phase 1 state and verify v0.0-foundation tag
2. Task 1: install & introspect DeepAgents/LangGraph API surface
