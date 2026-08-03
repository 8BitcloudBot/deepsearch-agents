# Phase 7 — Persistence and Recovery

**Status:** Not started
**Entry Gate:** Phase 6 event/trace contract and storage ADR

## Goal

让长任务在进程重启、网络断开和暂时性外部故障后按明确语义恢复，且不产生重复副作用。

## Deliverables

- `TaskStore`、`EventStore`、`CheckpointStore`；
- 幂等键、重试分类和降级；
- 服务重启恢复；
- WebSocket 按事件游标续传；
- 故障注入与恢复报告。

## Minimum Acceptance

进入实现前用 ADR 选择 SQLite 或 PostgreSQL；恢复测试证明终态、事件和 artifact 不重复。

## Non-goals

不在本阶段增加人工审批或完整预算策略。
