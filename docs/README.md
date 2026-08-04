# Project Documentation

本目录按“路线、当前状态、阶段方案、决策、证据、历史”分层。后续开发者和
Agent 应按以下顺序读取：

1. [务实封版执行入口](pragmatic-closure.md)：当前唯一任务顺序、范围和停止条件。
2. [当前阶段状态](phase-status.md)：实时进度与当前阻塞来源。
3. [整体开发路线](roadmap.md)：项目目标、发布线和 Phase 0-9 边界。
4. [阶段实施文档](phases/)：每个 Phase 的交付、非目标和最小验收。
5. [架构决策](adr/)：仍然生效的不可逆或跨阶段设计决策。
6. [验收证据](verification/)：命令输出、失败复现和历史验收记录。

`docs/superpowers/plans/`、`docs/superpowers/specs/` 和 `docs/handoffs/`
保留为历史设计、旧执行计划和交接记录。除非
[当前阶段状态](phase-status.md) 明确链接其中某份文件，否则它们不是现行实施指令。

## 文档维护规则

- `phase-status.md` 只记录当前事实，不累计完整历史。
- `roadmap.md` 只在项目目标、Phase 边界或发布线改变时更新。
- `phases/` 描述可独立验收的用户价值，不记录逐函数实现步骤。
- 测试数量只写入一次性的 verification 记录，不作为长期状态字段。
- 历史 rejection、旧 commit 和旧测试输出不得改写成当前结论。
- 当前 Phase 未通过验收时，不开始下一 Phase；同一 Phase 内允许按垂直切片推进。
