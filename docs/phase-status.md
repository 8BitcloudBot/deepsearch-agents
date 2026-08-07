# Current Phase Status

**Updated:** 2026-08-07

**Current Phase:** Phase 2 — Tutorial Parity

**Current Package:** Phase 2C — Release Evidence

**Baseline (accepted 2A checkpoint):** `1d6166c`
**Actual HEAD at B8 review:** `8dec2b7`（B1–B7 工作树未提交，按计划不在 Reasonix 内 commit）
**Target Tag:** `v0.1-tutorial-parity`（已存在，指向 `50680e6`；本轮未创建或移动）

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

当前执行 Phase 2B Safety Hardening，按 B1→B8 独立 Reasonix 节点推进。B1–B7 已
在本节点由 B8 全量门禁复核：task lifecycle、WebSocket disconnect/overflow、
HTTP 负向契约、thread isolation、download containment、文件解析/报告原子清理、
Provider 失败脱敏与测试责任清理均通过。B8 全新运行：后端 E2E 1 passed、
integration/unit 355 passed / 9 skipped、前端 vitest 60 passed / eslint / build、
ruff check / format 与 `git diff --check` 全部干净。唯一 RED 为
`pre-commit run --all-files` 中 detect-secrets 钩子要求刷新 `.secrets.baseline`
行号（B6 使 `test_external_adapters.py` 中 fake-key 条目行号 23→39，无新
secret）；`.secrets.baseline` 已按钩子要求刷新。Codex 已于 2026-08-07
独立重跑全部门禁，结果与 B8 一致；Phase 2B 正式 accepted。

## Package Status

| Package | Status | Exit condition |
|---|---|---|
| Phase 2A — Demo Closure | accepted | 后端闭环、React Workbench 与桌面/移动 browser smoke 通过 |
| Phase 2B — Safety Hardening | accepted | B1–B8 门禁与 baseline 通过 |
| Phase 2C — Release Evidence | active（下一节点） | 文档、CI、最终门禁与用户验收 |

Phase 3 未开始。Phase 2C 已正式启动。本轮不创建或移动任何 tag。

## Active Documents

- [整体路线](roadmap.md)
- [Phase 2 实施文档](phases/phase-2-tutorial-parity.md)
- [Phase 2A 实施补充规范](phases/phase-2a-implementation-addendum.md)
- [Phase 2B 执行计划](superpowers/plans/2026-08-07-phase-2b-safety-hardening.md)
- [Phase 2 验收证据](verification/phase-2-evidence.md)

旧 plans、specs 和 handoffs 仅作历史记录，不是当前执行指令。
