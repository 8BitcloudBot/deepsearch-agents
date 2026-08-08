# Phase 5 — Orchestration Experiments

**Status:** Not started
**Entry Gate:** Phase 4.5 live-source showcase is accepted, with offline and
real-run evidence strictly separated

## Goal

在相同数据、模型和预算下比较不同 Agent 编排策略是否带来可测收益。
所有策略必须复用 Phase 4.5 的 DeepAgents 多来源研究业务流和交付接口。

## Deliverables

- S0 Single Agent；
- S1 Orchestrator-Workers；
- S2 Router-Workers；
- S3 Planner-Executor-Reviewer；
- S4 Parallel Research + Reviewer；
- 统一策略接口、消融开关和质量/成本/延迟/失败报告。
- 对 Tavily、MySQL、RAGFlow、上传文件、引用定位与 Markdown/PDF 交付采用同一
  场景协议，不另建脱离产品流程的评测平台。

## Minimum Acceptance

所有策略使用同一评测协议；没有可测收益的策略不进入默认产品路径。

## Non-goals

不为展示策略数量而保留无收益复杂度，不替换 DeepAgents 技术主线，不提前实现
恢复或审批。
