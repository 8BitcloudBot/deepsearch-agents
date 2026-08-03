# Current Phase Status

**Updated:** 2026-08-01

**Current Phase:** Phase 2 — Tutorial Parity

**Current Package:** Phase 2A — Demo Closure

**Repository HEAD at review:** `397ae23`
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

最近一次独立专项检查中，E2E 未观察到 Knowledge Provider 工具事件，因此 Phase 2A
尚未通过。该失败必须通过修复运行链路或稳定测试装配解决，不得删除或放宽三类
Provider 的闭环要求。

## Package Status

| Package | Status | Exit condition |
|---|---|---|
| Phase 2A — Demo Closure | in progress | 后端闭环与 React Workbench 可演示 |
| Phase 2B — Safety Hardening | pending | 核心安全及高风险生命周期边界通过 |
| Phase 2C — Release Evidence | blocked by 2A/2B | 文档、CI、最终门禁与用户验收 |

Phase 3 未开始。当前 Phase 2A 未通过前，不创建 `v0.1*` tag。

## Active Documents

- [整体路线](roadmap.md)
- [Phase 2 实施文档](phases/phase-2-tutorial-parity.md)
- [Phase 2 验收证据](verification/phase-2-evidence.md)

旧 plans、specs 和 handoffs 仅作历史记录，不是当前执行指令。
