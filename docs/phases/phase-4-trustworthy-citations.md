# Phase 4 — Trustworthy Citations

**Status:** Not started
**Entry Gate:** Phase 3 fixed dataset and evaluation runner

## Goal

让报告中的关键声明能够定位来源、判断支持关系并暴露冲突、过期和不支持状态。

## Deliverables

- `EvidenceItem`、`Claim` 和来源等级模型；
- 规则与语义支持检查；
- 引用定位、冲突和版本状态；
- 前端引用面板；
- Citation Precision、Recall、Entailment 和 Unsupported Claim Rate 报告。

## Minimum Acceptance

在 Phase 3 固定数据上复现指标，失败声明可追溯到具体规则或模型判断。

## Non-goals

不同时实现所有编排策略、完整观测系统或持久化。
