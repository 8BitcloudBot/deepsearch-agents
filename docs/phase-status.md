# Current Phase Status

**Updated:** 2026-08-07

**Current Phase:** Phase 2 — Tutorial Parity

**Current Package:** Phase 2A — Demo Closure

**Repository HEAD at review:** `198b0c7`
**Target Tag:** `v0.1-tutorial-parity`（尚未创建）

## Accepted Baseline

| Phase | Status | Evidence |
|---|---|---|
| Phase 0 — Foundation | accepted | `v0.0-foundation` |
| Phase 1 — Capability Examples | accepted | `v0.0-deepagents-examples` |
| Phase 2 Tasks 0-4 | accepted | contracts, providers, tools, workspace and runtimes |

## Current Work

Phase 2 后端主体已经存在，包括三类 Provider、文件与报告工具、Agent Runtime、
FastAPI、WebSocket 和 TaskRegistry。当前优先目标不是继续扩展内部契约，而是完成
可演示的 Phase 2A 垂直闭环：

```text
上传约束文件 → 建立 WebSocket → 启动研究任务
→ Web/Catalog/Knowledge 工具事件 → Markdown/PDF
→ React 预览与下载 → 明确终态
```

在 HEAD `198b0c7` 上重新执行的专项门禁全部通过：E2E 闭环测试观察到 Web
（`internet_search`）、Catalog（`list_sql_tables`）、Knowledge
（`list_knowledge_assistants`）三类 Provider 工具事件、恰好一个 `task_completed`
终态，约束文件上传成功，两个报告生成并可列出/下载，后端闭环保持验收。

React Workbench（切片 F1–F4）已在 HEAD `198b0c7` 之上的工作区实现（未提交）；另补充了本地 Vite 开发 origin 的 API CORS 允许项：
类型化契约与传输助手、会话/健康头、约束上传、任务提交/取消、WebSocket 事件时间线、
running/success/failed/cancelled/connection-error 状态、Markdown 纯文本预览与
Markdown/PDF 下载。**F5 门禁本轮重新执行**：前端 Vitest 60 passed、ESLint 与生产
build 均 exit 0；后端 e2e 1 passed、integration/unit 265 passed/9 skipped、
ruff check/format、pre-commit 3/3、`git diff --check` 全部通过。

**浏览器 smoke（1440px/375px）已通过**：两个 viewport 均完成本地 mock health、
WebSocket、约束上传、任务启动、28 个按 sequence 排序的完整事件、Web/Catalog/
Knowledge Provider 工具、唯一 `task_completed`、Markdown 预览和报告下载验证；
页面宽度分别满足 `scrollWidth == clientWidth`。Phase 2A Demo Closure 已验收。

## Package Status

| Package | Status | Exit condition |
|---|---|---|
| Phase 2A — Demo Closure | accepted | 后端闭环、React Workbench 与桌面/移动 browser smoke 通过 |
| Phase 2B — Safety Hardening | pending | 核心安全及高风险生命周期边界通过 |
| Phase 2C — Release Evidence | blocked by 2A/2B | 文档、CI、最终门禁与用户验收 |

Phase 3 未开始。下一节点为 Phase 2B Safety Hardening；当前仍不创建 `v0.1*` tag。

## Active Documents

- [整体路线](roadmap.md)
- [Phase 2 实施文档](phases/phase-2-tutorial-parity.md)
- [Phase 2A 实施补充规范](phases/phase-2a-implementation-addendum.md)
- [Phase 2 验收证据](verification/phase-2-evidence.md)

旧 plans、specs 和 handoffs 仅作历史记录，不是当前执行指令。
