# Current Phase Status

**Updated:** 2026-08-16

**Branch:** main（当前工作树未提交）

**Portfolio release:** v1.0-portfolio（Phase 9 历史发布边界）

**Current package:** 三方证据多轮研究助手重构，schema 5.0.0

## Current Facts

当前产品已从一次性多来源研究任务收敛为多轮对话助手。用户登录后创建和切换会话，每轮可决定是否使用 Web；本地知识库始终启用，会话文件存在时自动参与。MySQL、结构化数据、旧 /api/task 工作流、schema 4.0.0、来源状态矩阵、PDF 和 JSON 下载已从当前产品源码及入口移除。历史运行目录不会被自动删除，但新版本不读取和展示。

~~~text
追问与本轮配置
  -> DeepAgents 一次有界研究计划
  -> LangGraph 固定检索图
  -> knowledge / session_file / web
  -> 代表性证据筛选与引用校验
  -> 自然语言回答
  -> SQLite 持久化与累计 Markdown 报告刷新
~~~

已实现的边界：

- TurnResearchPlan 最多包含 3 个子问题和 2 个知识库查询；普通模式最多执行 2 个 Web 查询，明确深入分析时最多 3 个。
- 三类来源按检索轮次并发；Web 查询并发执行，本地 Qdrant Local 查询在同一索引实例内串行以避免并发访问失败。
- 覆盖充分时跳过覆盖模型；只有查询无命中、启用来源缺失或去重证据少于 4 条时才执行一次有界审阅，补充查询整轮最多 2 个。
- 最近对话上下文限制为 6 轮；普通模式最多交付 6 条引用证据，深入模式最多 8 条，最终结果不保留未引用候选。
- Qdrant Local 使用 dense + sparse 候选与 RRF 融合，知识 chunk 和会话文件 chunk 使用稳定 ID。
- 会话文件以用户、会话和附件标识隔离；移除文件只影响后续回合。
- SQLite 保存用户、随机盐密码哈希、登录令牌哈希、会话、回合、附件和报告索引。
- admin 和 user 为本地演示初始账号；普通用户只能访问自己的数据。
- WebSocket 仅发送 turn.started、stage.changed、answer.delta、evidence.ready、report.updated、turn.completed 和 turn.failed；检索阶段只聚合公开启用的来源类型。
- 每个会话只提供 research-report.md；报告从已完成回合确定性重建并原子替换，逐轮只保留问题、限制、回答和声明，末尾只有一个去重证据附录。
- `/health` 从实际运行时构建结果返回 model、knowledge、web 和 session_file 能力状态；启动命令显式加载 `.env`。

当前实现已完成后端合同、前端会话工作台、报告去重、真实能力状态和旧生产架构清理。完整离线门禁、桌面/移动浏览器检查及一次明确授权的十题真实模型/Tavily 验收均已通过；十轮报告低于 45 KB，性能目标满足。MySQL 未连接或恢复。精确命令、计数和实时验收元数据见 [schema 5.0 质量优化证据](verification/schema5-quality-optimization.md)。

## Product Direction

研究证据只来自三方：本地知识库、当前会话文件和可选 Web。评测数据集、确定性 runner、指纹和引用指标继续作为行为证据，但不替代对话研究体验。

## Accepted Baseline

| Stage | Status | Canonical evidence |
|---|---|---|
| Phase 0 — Foundation | accepted | v0.0-foundation |
| Phase 1 — Capability Examples | accepted | v0.0-deepagents-examples |
| Phase 2 — Tutorial Parity | accepted historical baseline | v0.1.1-tutorial-parity |
| Phase 3 — Research Evaluation | accepted | Phase 3 evidence |
| Phase 4 — Trustworthy Citations | accepted | Phase 4 evidence |
| Phase 4.5 — Research Showcase | released historical baseline | v0.2-portfolio-showcase |
| Phase 9 — Portfolio Release | accepted historical boundary | v1.0-portfolio |
| Conversation Research schema 5.0.0 | implemented and verified in current worktree | [quality optimization evidence](verification/schema5-quality-optimization.md) |

## Development Boundary

- 仅由当前 Codex 会话开发，不调用其他 coding worker 或派生代理。
- 真实模型、Tavily、live 数据和其他 Provider 需要单独明确授权。
- 不连接或恢复 MySQL；所有资源访问仅按允许列表执行。
- 不提交、不推送、不发布、不部署。
- 完成声明前必须运行与 package 风险相称的后端、前端、静态和浏览器门禁。

## Canonical Documents

- Repository instructions
- Documentation index
- Roadmap
- Phase 9 historical boundary

历史 plans、specs、handoffs 和 evidence 仅保留其原始语境，不是当前执行指令。
