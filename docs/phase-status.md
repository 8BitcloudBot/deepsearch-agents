# Current Phase Status

**Updated:** 2026-08-07

**Current Phase:** Phase 2 — Tutorial Parity（accepted）

**Current Package:** Phase 2C — Release Evidence（accepted）

**Baseline (accepted 2A checkpoint):** `1d6166c`
**Actual HEAD at B8 review:** `8dec2b7`（B1–B7 工作树未提交，按计划不在 Reasonix 内 commit）
**Current accepted HEAD:** `2d8698a`
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

Phase 2B Safety Hardening 已正式 accepted（B1→B8 独立节点推进，Codex 独立重跑
门禁结果一致；B8 全量门禁：后端 E2E 1 passed、integration/unit 355 passed /
9 skipped、前端 60 passed / eslint / build、ruff 与 `git diff --check` 干净；
`pre-commit` detect-secrets 的 `.secrets.baseline` 行号刷新已按钩子要求提交）。

Phase 2C Release Evidence 以 `fb17a39` 为起始 baseline，并在 `2d8698a` 完成验收：已产出
[本地 mock 复现 runbook](runbooks/phase-2-tutorial-parity.md)，覆盖前置条件、
mock quick start、上传/任务/WebSocket/产物下载工作流、可选 MySQL 与真实
Provider smoke 前置条件，以及精确验证命令；README 已链接该 runbook。C2 节点
已在当前工作树独立重跑全部 11 项门禁并全部 GREEN（结果与 B8 记录逐项一致，
见 [验收证据](verification/phase-2-evidence.md)），门禁未改动任何文件；B8
唯一的 RED（detect-secrets baseline 行号刷新）已随 `fb17a39` 提交而关闭。
未创建或移动 tag；已有 tag `v0.1-tutorial-parity`（tag object `50680e6c`，
peel 至 commit `e29a80e`）保持不变。Phase 2C 已验收，但 tag 创建或移动仍需
单独明确授权。
C4 fresh mock quick start 已通过；MySQL `6 skipped` 的 pytest 原因为
`PHASE2_MYSQL_INTEGRATION` 未设置，同时当前 Docker daemon 权限不可用；真实
Provider/model `3 skipped` 的直接原因为 smoke opt-in flags 未设置，所需凭据也缺失。
用户已将独立验收委托给 Codex；最新验收
再次确认 E2E 1 passed、后端 355 passed / 9 skipped、前端 60 passed，以及全部
静态、构建、Compose、doctor 和 secret gates 为 GREEN。Phase 2C accepted。

## Package Status

| Package | Status | Exit condition |
|---|---|---|
| Phase 2A — Demo Closure | accepted | 后端闭环、React Workbench 与桌面/移动 browser smoke 通过 |
| Phase 2B — Safety Hardening | accepted | B1–B8 门禁与 baseline 通过 |
| Phase 2C — Release Evidence | accepted | 文档、CI parity、最终门禁与委托用户验收通过 |

Phase 3 ready、尚未开始。本轮不创建或移动任何 tag；现有 tag 的处置仍需明确授权。

## Active Documents

- [整体路线](roadmap.md)
- [Phase 2 实施文档](phases/phase-2-tutorial-parity.md)
- [Phase 2A 实施补充规范](phases/phase-2a-implementation-addendum.md)
- [Phase 2B 执行计划](superpowers/plans/2026-08-07-phase-2b-safety-hardening.md)
- [Phase 2C 复现 runbook](runbooks/phase-2-tutorial-parity.md)
- [Phase 2 验收证据](verification/phase-2-evidence.md)

旧 plans、specs 和 handoffs 仅作历史记录，不是当前执行指令。
