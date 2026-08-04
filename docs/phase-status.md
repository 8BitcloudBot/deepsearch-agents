# Current Phase Status

**Updated:** 2026-08-04

**Current Phase:** Phase 2 — Tutorial Parity

**Status:** B1-B4 已按顺序执行完毕：B1/B2/B3 通过；**B4 evidence-only
finalization 已提交 `ed4552f8f3b82ddd4cf097a9c70322a3f46e3215`（parent
`27832bc`）并 push 至 `codex/phase2a-websocket-e2e`**，GitHub Actions
push run **30907212389**（head ed4552f）**success**；
`v0.1-tutorial-parity` 未创建、未 release，
Phase 3-9 deferred

**Task 7 head（历史 gate）：** `98394404`（Task 7 提交已 push；GitHub
Actions push run 30878728964，head 9839440，**success**：Python 3.12
全步骤 + frontend Node 22 + pnpm 10 frozen install / Chromium install /
Vitest / lint / build / Playwright browser tests 全绿）。
**B3/B4 baseline（已验证）：** `27832bc5c3ba31d23a77e3187bf9e0e016a504c4`
（parent `9839440`）已 push；GitHub Actions push run **30906797763**，
head 27832bc，**success**：Python 3.12 install/tests/lint/format/
pre-commit/compose/doctor 全绿 + frontend Node 22 + pnpm 10 frozen
install / Chromium install / Vitest / lint / build / Playwright browser
tests 全绿。该提交包含 B3 测试与初始 B4 文档。
**Evidence finalization baseline（已验证）：**
`ed4552f8f3b82ddd4cf097a9c70322a3f46e3215`（parent `27832bc`）已 push；
GitHub Actions push run **30907212389**（head ed4552f）**success**。该提交仅
刷新证据文档，不改变 runtime/test behavior。
**Target Tag:** `v0.1-tutorial-parity`（**尚未创建**）

> B4 的 evidence-only 状态刷新已提交为 `ed4552f`，并由 push run
> 30907212389 验证；这不是 runtime/test behavior 变更。

## Accepted Baseline

| Phase | Status | Evidence |
|---|---|---|
| Phase 0 — Foundation | accepted | `v0.0-foundation` |
| Phase 1 — Capability Examples | accepted | `v0.0-deepagents-examples` |
| Phase 2 Tasks 0-6 | accepted | 见下表（真实 SHA） |
| Phase 2 Task 7 | completed；已 push，远端 head `98394404`；B1 CI（run 30878728964）通过 | 本文档、`docs/phase-2-tutorial.md`、`docs/verification/phase-2-evidence.md`、`.github/workflows/ci.yml` |
| Phase 2 B3/B4 | B3 + 初始 B4 committed `27832bc`；evidence finalization committed `ed4552f`；push run 30907212389 success | B3 测试文件（integration + e2e）+ B4 文档（README / phase-status / evidence / CHANGELOG） |

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
| B3/B4 | Failure/cancel/rerun closure 测试 + 初始 B4 文档 | `27832bc5c3ba31d23a77e3187bf9e0e016a504c4`（parent `9839440`；push run 30906797763 success） |

## Task 7 Local Gate（2026-08-03，历史）

> 以下为 Task 7 时的本地门禁记录，是历史证据；B1 之后实际 Ubuntu CI
> （Node 22 + pnpm 10）已运行并通过（run 30878728964，head 9839440；
> B3/B4 提交后由 run 30906797763 再次全绿），"CI 尚未运行"的表述不再
> 适用于当前状态。最新数字见
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
| B1 — Ubuntu CI gate | **completed** | Task 7 状态：push run 30878728964（head 9839440）success（历史 gate）；B3/B4 提交后由 push run 30906797763（head 27832bc）再次全绿 |
| B2 — Reproducible happy path | **completed**（本地） | 后端 API/WS closure 1 passed；mock integration 30 passed；desktop Playwright happy path 1 passed；默认 mock 模式从输入到 Markdown/PDF 预览和下载可复现 |
| B3 — Failure/cancel/rerun | **completed；已提交 `27832bc`，远端 CI 通过** | 全量 Python 353 passed/11 opt-in skips；B3 focused 11 passed；Vitest 24 passed；desktop Playwright 3 passed/1 project skip；Starlette httpx deprecation warning 仍在；提交 27832bc 的 push run 30906797763 success（含 B3 测试的远端 CI 覆盖） |
| B4 — Evidence closure | **completed；finalization 已提交 `ed4552f`，远端 CI 通过** | 本文档、README、evidence、changelog 事实与边界一致（mock 默认 / opt-in / deferred 明确）；push run 30907212389 success |

**Phase 3 未开始。** 目标 tag `v0.1-tutorial-parity` 尚未创建、未 release；
用户最终发布验收（创建 tag / release）仍未进行。

## Known Gate Gap

- **B3/B4 CI 已关闭（2026-08-04）：** B3 测试（`tests/integration/phase2/test_failure_cancel_rerun.py`、
  `tests/e2e/phase2/test_failure_cancel_rerun_closure.py`）与初始 B4 文档已提交为
  `27832bc5c3ba31d23a77e3187bf9e0e016a504c4`（parent `9839440`）并 push；
  GitHub Actions push run 30906797763（head 27832bc）**success** —— Python
  3.12 install/tests/lint/format/pre-commit/compose/doctor 与 frontend
  Node 22 + pnpm 10 frozen install / Chromium install / Vitest / lint /
  build / Playwright browser tests 全绿。此前"B3/B4 未提交、无远端 CI
  覆盖"的 gap 已关闭（仅指提交前状态，见 evidence 文档历史节）。
- 既有 B1 gate（run 30878728964，head 9839440）为 Task 7 状态的历史证据；
  此前本地 Homebrew Node 22（v22.23.2）+ pnpm 11.9.0 的聚焦重跑保留为
  历史兼容性证据（见 evidence 文档）。
- 外部真实服务 smoke（Tavily / RAGFlow / 真实模型）默认跳过，需要显式
  opt-in 与凭据；本次验收未运行。
- 默认启动为全 mock 模式（runtime + web + catalog + knowledge 均 "mock"），
  无需 API key；真实 provider 均为显式 opt-in。

## Pragmatic Closure

执行入口是 [`docs/pragmatic-closure.md`](pragmatic-closure.md)。B1-B4 已按顺序
执行完毕：

1. B1：Task 7 提交的 Ubuntu CI 已通过（push run 30878728964，head 9839440）；
2. B2：mock provider 正常路径已复现（API/WS closure 1 passed、mock integration 30 passed、desktop happy path 1 passed）；
3. B3：provider failure、cancel、failure 后 rerun 已复现并验证终态（全量 353 passed/11 skips、B3 focused 11 passed、Vitest 24 passed、desktop Playwright 3 passed/1 project skip）；
4. B4：本文档与 README、evidence、changelog 已统一事实与边界；初始 B4 文档随 B3 一并提交于 `27832bc`。

**B3/B4 已提交并获远端 CI 覆盖：** commit
`27832bc5c3ba31d23a77e3187bf9e0e016a504c4`（parent `9839440`）已 push 至
`codex/phase2a-websocket-e2e`；GitHub Actions push run **30906797763**
（head 27832bc）**success**：Python 3.12 install/tests/lint/format/
pre-commit/compose/doctor 全绿 + frontend Node 22 + pnpm 10 frozen
install / Chromium install / Vitest / lint / build / Playwright 全绿。

**下一步（需要用户）：** 用户最终发布验收 —— 创建 `v0.1-tutorial-parity`
tag 与 release（尚未进行）。`ed4552f` 的 evidence-only 状态刷新已提交并由
push run 30907212389 验证，不改变 runtime/test behavior。

本轮封版不实现 Phase 3-9 的可信引用、复杂评测、持久化恢复、审批和成本治理。旧 plans、specs 和 handoffs 只作历史参考。

## Active Documents

- [务实封版唯一执行入口](pragmatic-closure.md)
- [Phase 2 教程 Runbook（第 8–14 章）](phase-2-tutorial.md)
- [整体路线](roadmap.md)
- [Phase 2 实施文档](phases/phase-2-tutorial-parity.md)
- [Phase 2 验收证据](verification/phase-2-evidence.md)

旧 plans、specs 和 handoffs 仅作历史记录，不是当前执行指令。
