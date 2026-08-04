# Current Phase Status

**Updated:** 2026-08-04

**Current Phase:** Phase 2 — Tutorial Parity

**Status:** B1-B4 已按顺序执行完毕：B1 远端 CI 通过；B2/B3 本地门禁通过；
**B3/B4 变更未提交**（等待用户验收后另行授权提交并再跑 CI）；
`v0.1-tutorial-parity` 未创建、未 release，Phase 3-9 deferred

**Base HEAD（本地）：** `1d1c577`（`codex/phase2a-websocket-e2e`；Task 7
文档/CI 本地提交）。
**远端 head：** `98394404`（Task 7 提交已 push；GitHub Actions push run
30878728964，head 9839440，**success**：Python 3.12 全步骤 + frontend
Node 22 + pnpm 10 frozen install / Chromium install / Vitest / lint / build /
Playwright browser tests 全绿）。
**Target Tag:** `v0.1-tutorial-parity`（**尚未创建**）

## Accepted Baseline

| Phase | Status | Evidence |
|---|---|---|
| Phase 0 — Foundation | accepted | `v0.0-foundation` |
| Phase 1 — Capability Examples | accepted | `v0.0-deepagents-examples` |
| Phase 2 Tasks 0-6 | accepted | 见下表（真实 SHA） |
| Phase 2 Task 7 | completed in local commit `1d1c577`；已 push，远端 head `98394404` | 本文档、`docs/phase-2-tutorial.md`、`docs/verification/phase-2-evidence.md`、`.github/workflows/ci.yml`；B1 CI（run 30878728964）通过 |

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
| Task 7 | Document, Verify, and Stop for Acceptance | `1d1c577`（本地提交；已 push，远端 head `98394404`） |

## Task 7 Local Gate（2026-08-03，历史）

> 以下为 Task 7 时的本地门禁记录，是历史证据；B1 之后实际 Ubuntu CI
> （Node 22 + pnpm 10）已运行并通过（run 30878728964），"CI 尚未运行"
> 的表述不再适用于当前状态。最新数字见
> [verification/phase-2-evidence.md](verification/phase-2-evidence.md)。

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
- 当时（Task 7）Ubuntu CI job 尚未运行；本地 Node 22 兼容重跑（Homebrew
  `node@22` v22.23.2 + pnpm 11.9.0）为当时的最新本地近似证据。该 gap
  已由 B1（远端 CI 实际通过）关闭。

## Current Closure Work（2026-08-04）

| Slice | Status | Result / exit condition |
|---|---|---|
| B1 — Ubuntu CI gate | **completed** | push run 30878728964（head 9839440）success：Python 3.12 全步骤 + frontend Node 22 + pnpm 10 frozen install / Chromium install / Vitest / lint / build / Playwright browser tests 全绿 |
| B2 — Reproducible happy path | **completed**（本地） | 后端 API/WS closure 1 passed；mock integration 30 passed；desktop Playwright happy path 1 passed；默认 mock 模式从输入到 Markdown/PDF 预览和下载可复现 |
| B3 — Failure/cancel/rerun | **completed**（本地，**未提交**） | 全量 Python 353 passed/11 opt-in skips；B3 focused 11 passed；Vitest 24 passed；desktop Playwright 3 passed/1 project skip；Starlette httpx deprecation warning 仍在；变更未提交 → 无远端 CI 覆盖 |
| B4 — Evidence closure | **completed**（本地，**未提交**） | 本文档、README、evidence、changelog 事实与边界一致（mock 默认 / opt-in / deferred 明确） |

**Phase 3 未开始。** 目标 tag `v0.1-tutorial-parity` 尚未创建、未 release；
用户独立验收并单独授权提交 B3/B4 变更和再跑 CI 后才会创建。

## Known Gate Gap

- **B1 已关闭（2026-08-04）：** 实际 Ubuntu CI job（Node 22 + pnpm 10，
  含 `playwright install --with-deps chromium`）已运行并通过（push run
  30878728964，head 9839440）。此前本地 Homebrew Node 22（v22.23.2）+
  pnpm 11.9.0 的聚焦重跑保留为历史兼容性证据（见 evidence 文档）。
- **B3/B4 未提交：** B3 测试文件（`tests/integration/phase2/test_failure_cancel_rerun.py`、
  `tests/e2e/phase2/test_failure_cancel_rerun_closure.py`）与 B3/B4 文档改动仍在
  工作树中（untracked / uncommitted），**未获远端 CI 覆盖**；需用户验收后
  另行授权提交并再跑 CI。
- 外部真实服务 smoke（Tavily / RAGFlow / 真实模型）默认跳过，需要显式
  opt-in 与凭据；本次验收未运行。
- 默认启动为全 mock 模式（runtime + web + catalog + knowledge 均 "mock"），
  无需 API key；真实 provider 均为显式 opt-in。

## Pragmatic Closure

执行入口是 [`docs/pragmatic-closure.md`](pragmatic-closure.md)。B1-B4 已按顺序
执行完毕：

1. B1：实际 Ubuntu Node 22 + pnpm 10 CI 已运行并通过（push run 30878728964，head 9839440）；
2. B2：mock provider 正常路径已复现（API/WS closure 1 passed、mock integration 30 passed、desktop happy path 1 passed）；
3. B3：provider failure、cancel、failure 后 rerun 已复现并验证终态（本地 11 passed；变更未提交）；
4. B4：本文件与 README、evidence、changelog 已统一事实与边界。

**下一步（需要用户）：** 用户验收 B1-B4 结果；验收后**另行授权**提交 B3/B4
测试与文档变更、再跑 CI。本次未获得提交/发布授权，不得 commit/push/tag/release。

本轮封版不实现 Phase 3-9 的可信引用、复杂评测、持久化恢复、审批和成本治理。旧 plans、specs 和 handoffs 只作历史参考。

## Active Documents

- [务实封版唯一执行入口](pragmatic-closure.md)
- [Phase 2 教程 Runbook（第 8–14 章）](phase-2-tutorial.md)
- [整体路线](roadmap.md)
- [Phase 2 实施文档](phases/phase-2-tutorial-parity.md)
- [Phase 2 验收证据](verification/phase-2-evidence.md)

旧 plans、specs 和 handoffs 仅作历史记录，不是当前执行指令。
