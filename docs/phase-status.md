# Current Phase Status

**Updated:** 2026-08-03

**Current Phase:** Phase 2 — Tutorial Parity

**Status:** `blocked_pending_node22_ci` — Task 7 本地完成；release/用户验收
**blocked** —— 在要求的 Ubuntu CI 前端门禁（Node 22 + pnpm 10，Playwright
Chromium）实际运行并通过之前不进入 acceptance

**Base HEAD:** `5988a8a`（`codex/phase2a-websocket-e2e`；Task 0-6 验收基线）。
Task 7 文档/CI 改动为**未提交**的工作树变更，不属于该 commit
**Target Tag:** `v0.1-tutorial-parity`（**尚未创建**）

## Accepted Baseline

| Phase | Status | Evidence |
|---|---|---|
| Phase 0 — Foundation | accepted | `v0.0-foundation` |
| Phase 1 — Capability Examples | accepted | `v0.0-deepagents-examples` |
| Phase 2 Tasks 0-6 | accepted | 见下表（真实 SHA） |
| Phase 2 Task 7 | completed in worktree（本地） | 本文档、`docs/phase-2-tutorial.md`、`docs/verification/phase-2-evidence.md`、`.github/workflows/ci.yml`（Task 7 改动为**未提交**的工作树变更；release/验收 blocked：Node 22 CI 前端门禁实际运行并通过前不验收，通过后由用户授权提交） |

## Task Completion (real SHAs)

| Task | 内容 | SHA（真实） |
|---|---|---|
| Task 0 | Freeze Phase 2 Contracts and Start Evidence | `6a5d15a` |
| Task 1 | Settings, Live Events, Deterministic Adapters | `c6af299` |
| Task 2 | Web, Controlled MySQL, RAGFlow Modules | `cba9315` |
| Task 3 | Safe Workspace and Report Delivery | `e74c64a` |
| Task 4 | Tutorial Deep Agent Runtime | `c5b579e` |
| Task 5 | FastAPI/WebSocket/Upload/Cancel/Download Closure | `400be59`（实现）；接受闭包 `905c572` |
| Task 6 | React Tutorial Workbench | `f5d08a7` |
| Task 7 | Document, Verify, and Stop for Acceptance | 未提交的工作树改动（README/CHANGELOG/docs/CI）；**不虚设 SHA** |

## Current Work

Phase 2 垂直闭环已全部完成并通过本地完整门禁：

```text
上传约束文件 → 建立 WebSocket → 启动研究任务
→ Web/Catalog/Knowledge 工具事件 → Markdown/PDF
→ React 预览与下载 → 明确终态
```

- `pytest tests/ -q`：**348 passed, 11 skipped**（skip 全部为诚实 opt-in：Phase 1/2
  真实模型 smoke、Tavily/RAGFlow external smoke、MySQL 集成门禁）
- Ruff check / format、pre-commit（ruff、ruff-format、detect-secrets）、
  `docker compose config` 全部通过
- 前端：Vitest 22 passed、lint、build、Playwright Chromium（2 passed + 2 个
  按 project 条件性跳过）全部通过
- MySQL：Compose mysql:8.0 健康；`010_tutorial.sql` 幂等引导（重复执行 exit 0）；
  `PHASE2_MYSQL_INTEGRATION=1` 集成测试 **6 passed**；`tutorial_reader`
  SELECT 可用、INSERT 被拒（ERROR 1142）；focused E2E 1 passed
- **Node 22 本地兼容门禁已通过，但 Ubuntu CI job 尚未运行**：除默认 Node
  v26.5.1 全量门禁外，另用 Homebrew `node@22`（v22.23.2）+ pnpm 11.9.0
  聚焦重跑前端门禁（offline frozen install、Vitest 22 passed、lint、build、
  Playwright 2 passed + 2 个按 project 条件性跳过），全部通过；
  `v0.1-tutorial-parity` 验收前仍需实际执行 Ubuntu CI 的 Node 22 + pnpm 10
  frontend job（含 Chromium + Playwright）

## Package Status

| Package | Status | Exit condition |
|---|---|---|
| Phase 2A — Demo Closure | completed in worktree（release blocked on Node 22 CI gate） | 后端闭环与 React Workbench 可演示 ✅ |
| Phase 2B — Safety Hardening | pending（acceptance 后按用户安排） | 核心安全及高风险生命周期边界通过 |
| Phase 2C — Release Evidence | pending（acceptance 后按用户安排） | 文档、CI、最终门禁与用户验收 |

**Phase 3 未开始。** 目标 tag `v0.1-tutorial-parity` 尚未创建；用户独立验收并
单独授权后才会创建。

## Known Gate Gap

- 本地已有 Homebrew Node 22（`/opt/homebrew/opt/node@22/bin/node`，
  v22.23.2）：用 `PATH=/opt/homebrew/opt/node@22/bin:$PATH` + pnpm 11.9.0
  （`COREPACK_ENABLE_NETWORK=0`）跑通离线 frozen install、Vitest 22 passed、
  lint、build、Playwright（2 passed + 2 个按 project 条件性跳过）。但实际
  Ubuntu CI job（Node 22 + pnpm 10，含 `playwright install --with-deps
  chromium`）**尚未运行** —— pnpm 10 本地未缓存、未尝试下载；该 CI 门禁仍
  是验收前必须执行的 gate。默认 shell 的 Node 仍是 v26.5.1（bundled
  v24.14.0），其全量门禁结果保留为原始近似证据。
- 外部真实服务 smoke（Tavily / RAGFlow / 真实模型）默认跳过，需要显式
  opt-in 与凭据；本次验收未运行。

## Active Documents

- [Phase 2 教程 Runbook（第 8–14 章）](phase-2-tutorial.md)
- [整体路线](roadmap.md)
- [Phase 2 实施文档](phases/phase-2-tutorial-parity.md)
- [Phase 2 验收证据](verification/phase-2-evidence.md)

旧 plans、specs 和 handoffs 仅作历史记录，不是当前执行指令。
