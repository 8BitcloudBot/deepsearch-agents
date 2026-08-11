# Project Documentation

本目录按“路线、当前状态、阶段方案、决策、证据、历史”分层。后续开发者和
Agent 应按以下顺序读取：

1. [仓库开发约束](../AGENTS.md)：Codex 执行、上下文和验证边界。
2. [当前阶段状态](phase-status.md)：唯一的实时进度与当前阻塞来源。
3. [整体开发路线](roadmap.md)：项目目标、发布线和 Phase 边界。
4. [Phase 4.5 阶段文档](phases/phase-4-5-research-showcase.md)：当前产品交付边界。
5. [Phase 4.5 执行计划](superpowers/plans/2026-08-08-phase-4-5-research-showcase.md)：当前 package 顺序与验收。

产品方向由 [ADR 0004](adr/0004-product-direction-and-codex-governance.md)
固定：评测和可信能力服务于多来源研究闭环，不替代产品主路径。

`docs/superpowers/plans/`、`docs/superpowers/specs/`、`docs/handoffs/` 和
`docs/verification/` 默认不进入新任务上下文。它们保留历史设计、旧执行计划、交接和
验收事实；除非 [当前阶段状态](phase-status.md) 精确链接某份文件，否则不得读取或执行。
同样，旧 ADR、Phase 2 runbook、Phase 1 示例说明和已关闭阶段补充文档中的旧 provider
词汇只属于明确标注的历史背景，不构成当前技术路线或配置指导。

当前唯一可执行计划是
[Phase 4.5 Research Showcase](superpowers/plans/2026-08-08-phase-4-5-research-showcase.md)；
Phase 4 及更早计划均已冻结为历史证据，Phase 5 尚未激活。

## 文档维护规则

- `phase-status.md` 只记录当前事实，不累计完整历史。
- `roadmap.md` 只在项目目标、Phase 边界或发布线改变时更新。
- `phases/` 描述可独立验收的用户价值，不记录逐函数实现步骤。
- 测试数量只写入一次性的 verification 记录，不作为长期状态字段。
- 历史 rejection、旧 commit 和旧测试输出不得改写成当前结论。
- 当前 Phase 未通过验收时，不开始下一 Phase；同一 Phase 内允许按垂直切片推进。
- 本地修改按风险运行最小充分验证；完整离线门禁只在 package 验收、CI 或发布前运行。
- 当前开发只由 Codex 完成；历史协作记录不构成未来执行授权。
