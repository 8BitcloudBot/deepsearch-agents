# Current Phase Status

**Updated:** 2026-08-07

**Current Phase:** Phase 2 — Tutorial Parity

**Current Package:** Phase 2B — Safety Hardening

**Repository HEAD at review:** `1d6166c`
**Target Tag:** `v0.1-tutorial-parity`（尚未创建）

## Accepted Baseline

| Phase | Status | Evidence |
|---|---|---|
| Phase 0 — Foundation | accepted | `v0.0-foundation` |
| Phase 1 — Capability Examples | accepted | `v0.0-deepagents-examples` |
| Phase 2 Tasks 0-4 | accepted | contracts, providers, tools, workspace and runtimes |

## Current Work

Phase 2A Demo Closure 已在 checkpoint `1d6166c` 验收：后端闭环、React Workbench、
三类 Provider、唯一 terminal、Markdown/PDF、前后端门禁以及 1440px/375px browser
smoke 全部通过。

当前执行 Phase 2B Safety Hardening，按 B1→B8 独立 Reasonix 节点推进。B1 聚焦
coroutine 进入前的取消竞态：立即取消必须只产生一个 `task_cancelled`，不得产生
success/failure，并必须清理 TaskRegistry。B1 accepted 后自动进入 active
cancellation、WebSocket、HTTP/thread、文件/报告、Provider 脱敏、测试整理和总验收。

## Package Status

| Package | Status | Exit condition |
|---|---|---|
| Phase 2A — Demo Closure | accepted | 后端闭环、React Workbench 与桌面/移动 browser smoke 通过 |
| Phase 2B — Safety Hardening | ready（B1 下一节点） | 核心安全及高风险生命周期边界通过 |
| Phase 2C — Release Evidence | blocked by 2A/2B | 文档、CI、最终门禁与用户验收 |

Phase 3 未开始。下一节点为 Phase 2B Safety Hardening；当前仍不创建 `v0.1*` tag。

## Active Documents

- [整体路线](roadmap.md)
- [Phase 2 实施文档](phases/phase-2-tutorial-parity.md)
- [Phase 2A 实施补充规范](phases/phase-2a-implementation-addendum.md)
- [Phase 2B 执行计划](superpowers/plans/2026-08-07-phase-2b-safety-hardening.md)
- [Phase 2 验收证据](verification/phase-2-evidence.md)

旧 plans、specs 和 handoffs 仅作历史记录，不是当前执行指令。
