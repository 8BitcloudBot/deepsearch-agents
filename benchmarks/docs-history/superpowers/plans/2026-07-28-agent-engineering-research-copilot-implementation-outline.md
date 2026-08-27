# Agent Engineering Research Copilot Implementation Outline

> **Historical plan:** superseded by [`docs/roadmap.md`](../../roadmap.md) and
> [`docs/phases/`](../../phases/). Retained for project-history reference.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to execute the selected phase task-by-task. Do not begin a later phase before the user explicitly accepts the current phase evidence.

**Goal:** 按 v3 设计从零实现 Agent Engineering Research Copilot，先完成可重复的教程基线，再逐步迁移到 AI Agent 技术研究领域，并最终形成可评测、可恢复、可追踪、可解释的 Agent 作品集项目。

**Architecture:** 保留教程的 `app/` Python 后端、`frontend/` React 前端、`docker/` 外部服务、`examples/` 学习示例和 `tests/` 测试边界。Phase 0-2 只完成基础设施与教程闭环；Phase 3 起替换数据和 Prompt；Phase 4-8 逐层增加引用验证、编排实验、可观测性、持久化、人工审批和预算治理。

**Tech Stack:** Python 3.12、uv、FastAPI、Pydantic、pytest、Ruff、React、Vite、TypeScript、pnpm、Docker Compose、MySQL、Tavily、RAGFlow、DeepAgents、LangGraph、WebSocket、SQLite/PostgreSQL（最终持久化方案在 Phase 7 前确定）。

## Global Constraints

- 当前阶段只执行用户明确授权的 Phase；未通过验收不得实现后续阶段。
- `v0.1-tutorial-parity` 必须能独立复现教程第 8-14 章，不将最终领域数据提前混入基线。
- `v0.2-portfolio-core` 才切换 `agent-research` profile，并加入固定数据、评测、引用、编排和基础 trace。
- `v0.3-reliable-runtime` 才加入任务/事件/checkpoint 持久化、恢复、审批和成本治理。
- Structured Data Agent 只处理研究目录的受控只读查询，不实现第二套 Text-to-SQL、字段召回或指标语义层。
- 所有真实 API 必须有 mock provider；离线测试不得依赖模型、Tavily 或 RAGFlow 网络可用。
- 所有外部资料、网页快照、PDF 和数据库 dump 必须记录来源、版本、抓取时间、内容哈希和许可证。
- 不允许把 API Key、Cookie、`.env`、数据库 volume、生成报告或个人文件提交到 Git。
- 所有任务都必须先更新 `docs/phase-status.md`，再修改代码；每个可交付任务都必须有对应测试和文档证据。
- Git 操作必须使用显式文件路径；禁止 `git add .`、强制推送、重写历史和删除用户未授权的数据。
- 每个任务结束后创建一个小而完整的 commit；commit message 使用 Conventional Commits。
- 没有实测结果不得写入简历数字；所有指标必须绑定数据版本、模型版本、Prompt 版本和代码 commit。

## Repository Layout

```text
deepsearch-agents/
├── app/                         # Python 后端和最终 Agent 代码
│   ├── agent/                   # 主 Agent、子 Agent、Prompt、模型适配
│   ├── api/                     # FastAPI、WebSocket、上下文和事件接口
│   ├── tools/                   # Web、MySQL、RAGFlow、文件和报告工具
│   ├── storage/                 # Phase 7 起的任务、事件、checkpoint 适配器
│   └── utils/                   # 路径、解析、脱敏和通用工具
├── frontend/                    # React + Vite 工作台
├── docker/                      # MySQL 和本地依赖配置
├── examples/                    # 教程章节最小示例
├── tests/                       # 单元、集成、端到端和评测测试
├── docs/                        # ADR、阶段状态、验收证据和运行说明
├── scripts/                     # 环境检查、数据快照和评测入口
├── output/                      # 运行时产物，仅保留 .gitkeep
└── updated/                    # 会话上传目录，仅保留 .gitkeep
```

## Phase Map

### Phase 0: Foundation and Execution Discipline

**目标：** 建立 Git、Python、前端、Docker、环境变量、测试、CI、密钥扫描和实时文档更新机制。

**交付：** 空项目可安装、可测试、可构建；MySQL health check 可运行；无真实 Key 时 mock 检查可通过；文档和 commit 规则生效。

**禁止：** DeepAgents 主 Agent、Tavily 实际调用、RAGFlow 业务知识库、教程业务数据、报告生成和复杂前端页面。

**验收 tag：** `v0.0-foundation`。

### Phase 1: DeepAgents Capability Examples

**目标：** 完成教程前置章节的最小示例：`invoke`、`stream`、chunk、子 Agent、兼容 Runnable、interrupt、store、memory、中间件和 Skills。

**交付：** 每个概念有独立示例、测试、运行命令和学习说明；示例不依赖最终产品目录。

**依赖：** Phase 0 通过。

**验收 tag：** `v0.0-deepagents-examples`。

### Phase 2: Tutorial Parity

**目标：** 按教程第 8-14 章完成一主三从、Web/MySQL/RAGFlow、文件交付、FastAPI、WebSocket 和 React 闭环。

**交付：** `tutorial` profile、教程请求/响应样例、工具事件、报告文件和失败证据。

**依赖：** Phase 1 通过；真实 RAGFlow 可以使用外部服务，离线测试使用 mock。

**验收 tag：** `v0.1-tutorial-parity`。

### Phase 3: Agent Research Domain and Evaluation Baseline

**目标：** 替换教程药品/通用样例为 AI Agent 技术研究数据，建立来源快照、研究目录、RAGFlow collection、`seed-10` 和 `dev-40`。

**交付：** `agent-research` profile、数据版本、评测 runner、S0/S1 对照结果。

**依赖：** Phase 2 tag；不修改教程 profile 的可复现结果。

### Phase 4: Trustworthy Citations

**目标：** 为报告引入声明模型、来源等级、版本检查、引用定位、支持关系检查和冲突状态。

**交付：** `EvidenceItem`、`Claim`、Verifier、引用面板、Citation Precision/Recall/Entailment 报告。

**依赖：** Phase 3 固定快照和评测样本。

### Phase 5: Orchestration Experiments

**目标：** 统一实现 S0 Single Agent、S1 Orchestrator-Workers、S2 Router-Workers、S3 Planner-Executor-Reviewer、S4 Parallel Research + Reviewer，并在相同预算下比较。

**交付：** 策略接口、配置切换、消融开关、质量/成本/延迟/失败类型报告。

**依赖：** Phase 4 能稳定评分；若某策略没有可测收益，不进入默认生产路径。

### Phase 6: Observability

**目标：** 建立版本化事件、结构化日志、trace/span、指标和前端运行详情。

**交付：** 从最终声明追溯到 Agent、Tool、Source、Token、费用和延迟的链路。

**依赖：** Phase 3 的事件语义和 Phase 5 的策略标识。

### Phase 7: Persistence and Recovery

**目标：** 选择并实现任务、事件、checkpoint、artifact 存储，支持幂等、重试、服务重启恢复和 WebSocket 事件续传。

**交付：** `TaskStore`、`EventStore`、`CheckpointStore`、恢复测试和故障注入报告。

**依赖：** Phase 6 trace/event 契约；进入本阶段前通过 ADR 固化 SQLite 或 PostgreSQL 方案。

### Phase 8: Human Approval and Cost Governance

**目标：** 加入计划审批、风险工具审批、报告发布审批和 Token/费用/时间/工具/并发预算。

**交付：** 审批状态机、预算策略、超限降级、恢复后的审批一致性测试。

**依赖：** Phase 7 持久化和恢复语义。

### Phase 9: Portfolio Release

**目标：** 固定 `portfolio-100` 和 `hidden-20`，完成演示、失败复盘、README、架构图、视频、STAR 和面试证据。

**交付：** `v1.0-portfolio`，不再新增核心架构能力。

**依赖：** Phase 8 通过，所有简历数字可由仓库命令重现。

## Release Gates

### `v0.0-foundation`

- Git 初始化、分支和 commit 规则可执行；
- Python、前端、Docker、MySQL health check 可重复运行；
- 后端 `/health`、前端最小页面和测试均通过；
- `.env` 和 secrets 不进入 Git；
- `docs/phase-status.md` 和验收证据已建立。

### `v0.1-tutorial-parity`

- 教程第 8-14 章映射表全部通过；
- `tutorial` profile 可重建；
- Web + MySQL + RAGFlow/mock + 文件报告闭环可运行；
- 基线接口请求样例、响应样例、事件和输出文件已保存。

### `v0.2-portfolio-core`

- `agent-research` profile 可运行；
- 固定快照、`seed-10`、`dev-40` 和至少三种编排策略可评测；
- 引用验证和基础 trace 有真实结果；
- 不包含第二套 Text-to-SQL 或未测量的收益承诺。

### `v0.3-reliable-runtime`

- 任务/事件/checkpoint 持久化；
- 重启恢复、事件续传、人工审批和预算硬限制通过故障测试；
- 恢复不会重复不可逆副作用；
- 所有关键事件和成本可追溯。

### `v1.0-portfolio`

- `portfolio-100` 和 `hidden-20` 评测报告完成；
- 3 个演示案例和至少 3 个失败复盘完成；
- README、运行文档、架构图、视频和 STAR 与代码一致；
- 功能范围冻结。

## Cross-Phase Documentation Rules

每次编码任务必须同步：

1. `docs/phase-status.md`：当前阶段、任务状态、最近 commit、阻塞项和下一步；
2. `docs/verification/<phase>-evidence.md`：命令、时间、环境、输出摘要和失败记录；
3. 相关 ADR：只记录已经做出的架构决策，不把未决定的选项伪装成结论；
4. README：只更新用户实际可执行的命令和当前已支持能力；
5. `CHANGELOG.md`：每个阶段 tag 记录新增能力、破坏性变更和已知限制。

文档更新与代码必须在同一个 commit 或同一组紧邻 commit 中完成。任何验收失败都要记录实际错误，不得删日志或只写“已修复”。

## Execution Protocol for DeepSeek

DeepSeek 每次只读取：

1. 本大纲；
2. 当前阶段精确计划；
3. v3 中与当前阶段相关的章节；
4. 当前 `docs/phase-status.md` 和最近验收证据。

DeepSeek 必须：

- 先输出将修改的文件清单和执行步骤，等待用户确认后再写代码；
- 只修改当前任务允许的文件；
- 先写测试，再写实现；
- 每个步骤执行计划中给出的命令；
- 把完整命令输出摘要写入验收证据；
- 任务完成后停止，不自行开始下一阶段；
- 遇到计划未覆盖的问题，记录为阻塞项并请求决策，不自行扩展范围。

DeepSeek 禁止：

- 自行新增依赖、服务、Agent、API 或数据库表；
- 以“更合理”为理由更改接口名、目录边界或版本策略；
- 跳过测试、secret scan、文档更新或 commit；
- 修改 v3、实施大纲或后续阶段计划；
- 把 mock 通过当成真实外部服务通过；
- 生成未由测试或固定数据支持的指标。

## Current Handoff

当前允许执行的唯一范围是 **Phase 0**。Phase 0 的逐任务计划见：

`docs/superpowers/plans/2026-07-28-agent-engineering-research-copilot-phase-0-plan.md`

Phase 0 验收通过并由用户明确确认后，才编写 Phase 1 精确实施计划。
