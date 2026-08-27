# Project Documentation

本目录按“当前事实、路线、阶段边界、决策和历史证据”分层。后续开发者和 Agent 默认只按以下顺序建立上下文：

1. [仓库开发约束](../AGENTS.md)
2. [当前阶段状态](phase-status.md)
3. [整体开发路线](roadmap.md)
4. [Phase 9 作品集边界](phases/phase-9-portfolio-release.md)

当前产品是 schema 5.0.0 的三方证据多轮研究助手。主路径为：

~~~text
对话追问
  -> DeepAgents 一次有界规划
  -> LangGraph 固定回合流程
  -> 本地知识库 + 可选会话文件 + 可选 Web
  -> 引用校验后的回答
  -> React 消息流 + 累计 Markdown 报告
~~~

MySQL、结构化数据、一次性 /api/task、旧来源状态矩阵、PDF 和 JSON 下载均不属于当前产品。SQLite 保存本地演示用户、认证会话、对话、回合、附件元数据和报告索引；Qdrant Local 负责全局知识库和会话文件检索。

Phase 9 是已验收的历史作品集发布边界。Phase 10 早期 schema 3.0.0/4.0.0 设计、历史计划和真实 Provider 验收记录保留为演进证据，不再是当前执行指令。当前实现事实只以 phase-status.md 为准。

docs/superpowers/plans/、docs/superpowers/specs/、docs/handoffs/ 和 docs/verification/ 默认不进入新任务上下文。只有当前 canonical 文档为具体问题精确链接某份记录时才读取；历史原文不得改写成当前合同。

## 文档维护规则

- phase-status.md 只记录当前事实，不累计命令输出或完整历史。
- roadmap.md 只记录项目目标、阶段边界和发布线。
- phases/ 描述可独立验收的用户价值，不记录逐函数实现步骤。
- 精确测试命令和数量写入单一 package evidence，不在长期文档间复制。
- 当前开发只由本 Codex 会话完成；历史协作记录不构成委派授权。
- 真实 Provider、live 数据、发布和部署均需单独明确授权。
