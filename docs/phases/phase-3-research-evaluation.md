# Phase 3 — Agent Research Domain and Evaluation Baseline

**Status:** Not started
**Entry Gate:** `v0.1-tutorial-parity`

## Goal

把已验证的教程闭环迁移到 AI Agent 技术研究领域，并建立第一个可复现评测基线。

## Deliverables

- `agent-research` profile，不破坏 `tutorial` profile；
- 版本化 Web 快照、研究目录和 RAGFlow 资料集；
- `seed-10` 与 `dev-40` 样本；
- 统一评测 runner；
- S0 Single Agent 与 S1 Orchestrator-Workers 基线报告。

## Minimum Acceptance

离线评测可重复运行，结果绑定数据、模型、Prompt 和 commit；报告同时记录成功、失败
与限制，不以 mock 结果冒充真实服务结果。

## Non-goals

不在本阶段实现完整引用验证、S2-S4、生产 trace、持久化或审批。
