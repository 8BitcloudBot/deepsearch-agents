# Agent Engineering Research Copilot 项目规划（v2）

> **Historical design:** 本文保留早期教程路线和 provider 选择的历史事实，不再作为
> 当前产品路线或执行指导。当前方向以 `docs/phase-status.md` 为准。

> 面向 AI Agent 框架选型、技术调研和工程决策的多智能体可信研究系统

| 项目属性 | 内容 |
| --- | --- |
| 文档状态 | 组合定位已收敛，待实施 |
| 文档日期 | 2026-07-28 |
| 目标岗位 | AI 应用工程师 / Agent 工程师 |
| 项目定位 | 简历中的 Agent 代表项目 |
| 技术属性 | 多智能体系统、Agentic RAG、长任务执行、可信研究 |
| 开发策略 | 忠实完成教程基线，再逐层增加差异化能力 |
| 质量目标 | 可运行、可评测、可恢复、可追踪、可解释、可演示 |
| 组合边界 | 本项目负责 Agent 编排与可靠执行，不负责通用 Text-to-SQL |

## 1. 执行摘要

Agent Engineering Research Copilot 是一个面向 AI Agent 技术研究场景的多智能体系统。用户可以提出框架选型、论文调研、工程方案比较、版本迁移和技术决策类问题。系统由主智能体拆解任务，并按需调度网络搜索、结构化数据库、私有知识库和文件分析等专家能力，最终生成带细粒度引用、证据状态和成本信息的研究报告。

项目以 didilili 的“深度研搜”教程为学习和基线实现路径。第一阶段尽量忠实复现教程的一主多从架构、FastAPI、WebSocket、RAGFlow、MySQL、文件处理和报告生成链路。基线通过验收后，再依次增加：

1. 固定版本的数据快照与 Agent 评测集；
2. 声明级引用验证和来源可信度分级；
3. 多种编排策略的对照与消融实验；
4. 结构化事件、指标、日志与全链路 trace；
5. 任务、事件与 checkpoint 持久化，以及失败恢复；
6. 人工审批、工具权限和安全边界；
7. Token、费用、延迟和工具调用预算治理；
8. 可复现的量化报告、演示案例和简历材料。

项目最终应被表述为“具备 Agentic RAG 能力的多智能体可信研究系统”，但在简历分类上属于 Agent 项目。RAG 是专家能力之一，核心技术叙事是复杂任务的规划、动态工具路由、可靠执行、验证与治理。

## 2. 背景与问题

AI Agent 技术信息分散在论文、官方文档、GitHub 仓库、Release Notes、Issue、Benchmark 和技术博客中。实际工程决策通常不能依赖单一来源。例如，判断一个框架是否适合长任务，需要同时确认：

- 官方文档声明的能力；
- 当前稳定版本和版本变化；
- 底层运行时的 checkpoint、interrupt 和 resume 机制；
- GitHub 中的实现状态、Issue 和 Release；
- 论文或 Benchmark 中的实验边界；
- 当前团队的约束、已有方案和上传材料。

普通搜索问答或单次 RAG 容易出现以下问题：

- 只返回相关文本，没有完成跨来源核对；
- 混淆不同版本的 API 和行为；
- 引用存在，但不能支撑对应声明；
- 对二手博客与官方资料不加区分；
- 长任务中断后无法恢复；
- 无法说明为什么调用某个工具或子智能体；
- 不记录 Token、成本、延迟和失败过程；
- 无法通过固定评测集证明架构改进有效。

本项目要解决的不是“让模型回答得更长”，而是让技术研究过程具备证据、版本、状态和可验证结果。

## 3. 项目目标

### 3.1 用户目标

系统应支持以下核心任务：

1. **框架选型**：根据场景和约束比较 LangGraph、DeepAgents、AutoGen、CrewAI、OpenAI Agents SDK 等方案。
2. **技术调研**：结合论文、官方文档、GitHub 和 Benchmark 生成结构化研究报告。
3. **工程决策**：输出候选方案、证据、约束、风险、推荐结论和待验证项。
4. **版本研究**：回答带 `as_of_date` 的版本、迁移和兼容性问题。
5. **材料联合分析**：将公开资料与用户上传的设计文档、评测结果或需求文件联合分析。
6. **报告交付**：生成 Markdown 和 PDF，并提供来源清单和运行摘要。

### 3.2 工程目标

- 使用主智能体与专家智能体完成动态规划和工具路由。
- 对网络、SQL、RAG 和文件工具建立统一调用契约。
- 对长任务提供实时事件、取消、暂停、恢复和重试能力。
- 对关键声明提供可定位、可验证、可回溯的引用。
- 对所有任务记录 trace、Token、费用、延迟和失败原因。
- 使用固定数据快照和评测集比较不同编排策略。
- 在本地 Docker Compose 环境中可重复启动和验证。
- 形成可公开演示、可应对面试追问的工程证据。

### 3.3 学习目标

- 理解 DeepAgents 与 LangGraph 在长任务、状态、子智能体和中间件中的职责边界。
- 理解动态 Agent 编排与确定性工作流的适用条件。
- 掌握 Agent 评测、引用验证、可靠执行和 AgentOps 基础方法。
- 能解释每项基础设施解决的具体问题，而不是堆叠技术名词。

## 4. 非目标

以下内容不进入首个可交付版本：

- 通用搜索引擎或全网爬虫；
- 自动抓取任何需要登录、付费或违反站点条款的内容；
- 面向所有行业的通用研究平台；
- 多租户 SaaS、计费、组织管理和复杂 RBAC；
- 在线多人协作编辑器；
- 自研向量数据库、搜索引擎或 Agent 框架；
- 无边界的自主浏览和无限递归研究；
- 以“模拟生产数据”包装真实企业使用经历；
- 在没有实验数据时声称准确率、成功率或成本收益。

## 5. 定位与差异化

### 5.1 简历定位

建议项目名称：

> Agent Engineering Research Copilot：面向 AI Agent 框架选型、技术调研和工程决策的多智能体可信研究系统

建议一句话描述：

> 基于 DeepAgents、LangGraph、FastAPI 和 React 构建多智能体研究系统，由主智能体动态调度网络搜索、结构化数据、私有知识库和文件分析能力，并通过引用验证、持久化恢复、人工审批和成本治理提升长任务可靠性。

### 5.2 为什么属于 Agent 项目

系统的核心问题是：

- 如何拆解开放式研究任务；
- 如何决定何时以及为何调用某个信息源；
- 如何并行或串行调度专家；
- 如何判断证据是否充分；
- 如何在失败、暂停或重启后继续；
- 如何验证结果并控制预算。

知识库检索只是其中一个工具，因此项目技术上属于 Agentic RAG，简历上应归类为 Agent 系统。

### 5.3 与教程基线的差异化

最终版本必须有以下可验证增量：

| 维度 | 教程基线 | 最终项目 |
| --- | --- | --- |
| 领域 | 多个教学主题混合 | AI Agent 工程研究 |
| 数据 | 动态搜索和少量样例 | 版本化快照、结构化目录、固定评测集 |
| 编排 | 一主三从 | 多策略可切换、可对照、可消融 |
| 引用 | 来源由模型组织 | 声明级引用、来源分级、自动验证 |
| 状态 | 会话上下文和内存执行 | 任务、事件、checkpoint 持久化与恢复 |
| 可观测性 | WebSocket 事件展示 | trace、指标、结构化日志、成本明细 |
| 人工介入 | 以自动执行为主 | 计划审批、风险工具审批、报告发布审批 |
| 评测 | 手工演示 | 固定数据、rubric、自动评分、回归门禁 |

### 5.4 与 Shopkeeper Analytics 的组合边界

本项目和 Shopkeeper Analytics 作为两项独立简历项目时，必须避免重复建设和重复叙事。

| 能力 | 本项目负责 | Shopkeeper Analytics 负责 |
| --- | --- | --- |
| 主问题 | 如何可靠完成开放式技术研究任务 | 如何把业务问题转换为正确 SQL |
| 核心 Agent | Planner、Research Workers、Citation Reviewer | Text-to-SQL 状态图和 SQL 修正节点 |
| 检索 | 多源证据、论文、官方文档、版本快照 | 字段、指标、字段值混合召回 |
| 数据库 | 受控查询研究目录，不做自然语言生成 SQL | 元数据建模、指标口径和 SQL 生成 |
| 可靠性 | checkpoint、恢复、审批、预算、事件回放 | SQL 安全、查询超时、结果限制、权限过滤 |
| 主要指标 | 任务成功率、引用质量、恢复率、成本 | SQL 语义正确率、字段 Recall@K、安全拦截率 |

Structured Data Agent 只允许使用预定义查询模板、只读查询或明确的研究目录 API，不实现第二套通用 Text-to-SQL。任何 SQL 生成、字段召回和指标口径能力都属于另一个项目的边界。

### 5.5 作品集叙事

简历和面试中按以下顺序展示：

1. **Research Copilot**：展示复杂 Agent 系统的规划、调度、验证、恢复和治理。
2. **Shopkeeper Analytics**：展示企业数据场景下的语义层、混合检索、Text-to-SQL 和 SQL 安全。

两个项目共用 Python、FastAPI 或 LangGraph 等基础技术并不是问题，但每个项目的结果指标、failure case 和核心设计决策必须不同。
| 安全 | 基础会话隔离 | SQL、文件、网页、Prompt Injection 防护 |

## 6. 用户与使用场景

### 6.1 目标用户

- 需要做 Agent 框架选型的 AI 应用工程师；
- 需要调研论文和工程实现的技术负责人；
- 需要形成架构决策依据的后端或平台工程师；
- 需要将内部方案与外部资料联合分析的研发人员。

### 6.2 核心用例

#### 用例 A：框架选型报告

> 截至 2026-07-01，对比 LangGraph、DeepAgents 和 OpenAI Agents SDK 在长任务状态恢复、人工审批、子智能体隔离和可观测性方面的能力。结合我上传的系统约束，给出推荐方案并生成 PDF。

预期行为：

- 从上传文件提取约束；
- 查询固定版本的官方文档；
- 查询版本和仓库元数据；
- 必要时检索最新官方资料；
- 对关键对比结论逐项给出引用；
- 标明事实、推断和建议；
- 输出决策矩阵、风险和待验证项。

#### 用例 B：版本迁移研究

> 某 Agent 框架从版本 X 迁移到版本 Y 时，状态持久化和工具调用接口有哪些破坏性变化？

预期行为：

- 优先使用 Release Notes、迁移指南和对应代码 tag；
- 拒绝混用其他版本文档；
- 对无法确认的变化标为“证据不足”；
- 给出迁移检查清单。

#### 用例 C：论文到工程实践

> 调研 Agent 记忆评测的代表性论文，并说明哪些指标可以落地到工程回归测试。

预期行为：

- 查询论文元数据和 PDF；
- 提取任务定义、数据集、指标和限制；
- 查询公开实现或官方仓库；
- 区分论文结论与系统建议。

#### 用例 D：冲突证据处理

> 官方文档、README 和 GitHub Issue 对同一能力描述不一致，当前稳定版本实际支持什么？

预期行为：

- 按来源等级、版本和时间排序证据；
- 展示冲突，而不是强行生成单一确定答案；
- 给出验证命令或最小实验建议。

## 7. 核心设计原则

1. **证据优先**：先收集和验证证据，再形成结论。
2. **版本优先**：技术事实必须包含版本或时间边界。
3. **显式不确定性**：证据不足、来源冲突和推断必须明确标注。
4. **可恢复执行**：长任务不依赖单个 HTTP 连接或单进程内存状态。
5. **最小权限**：工具默认只读，扩大权限需要策略或人工审批。
6. **预算有限**：递归深度、并发数、Token、费用和时间都有硬上限。
7. **评测先于宣传**：所有简历指标来自固定版本、固定配置的真实运行。
8. **基线可比较**：每项优化都应与教程基线或更简单方案对照。
9. **失败可解释**：错误必须能定位到计划、Agent、工具、来源或模型阶段。
10. **实现原创**：教程用于学习和对照，代码、测试、数据治理和增强功能独立实现。

## 8. 总体架构

```text
React Research Workspace
  ├── 任务输入 / 文件上传 / 研究配置
  ├── 实时计划与事件流
  ├── 证据和引用检查面板
  ├── 人工审批
  └── 报告预览与下载
              │ HTTP + WebSocket
              ▼
FastAPI Service
  ├── Task API
  ├── File API
  ├── Approval API
  ├── Report API
  └── WebSocket Event Gateway
              │
              ▼
Research Runtime
  ├── Task State Machine
  ├── Orchestration Strategy
  ├── Policy / Budget Middleware
  ├── Checkpoint / Resume
  └── Event & Trace Recorder
              │
              ▼
Main Research Agent
  ├── Web Research Agent
  ├── Structured Data Agent
  ├── Knowledge Base Agent
  ├── File Analysis Agent
  └── Citation Reviewer Agent
              │
              ▼
Tool & Data Layer
  ├── Tavily / Web Snapshot Store
  ├── MySQL Research Catalog
  ├── RAGFlow Knowledge Base
  ├── Session File Workspace
  └── Markdown / PDF Generator
              │
              ▼
Platform State
  ├── Relational Task Store
  ├── Event Store
  ├── Checkpoint Store
  ├── Artifact Store
  └── Telemetry Backend
```

### 8.1 模块边界

| 模块 | 职责 | 不负责 |
| --- | --- | --- |
| API 层 | 协议、校验、鉴权入口、流式连接 | Agent 决策 |
| Runtime | 状态机、策略、恢复、预算、事件 | 具体来源查询 |
| Main Agent | 任务理解、计划、调度、综合 | 直接访问数据库连接 |
| Subagent | 在明确领域内完成研究子任务 | 控制全局预算和最终发布 |
| Tool | 确定性外部操作和结果规范化 | 自主规划 |
| Verifier | 声明、引用和证据检查 | 生成新的未经检索事实 |
| Storage | 持久化和查询 | 业务推理 |
| Frontend | 展示、审批、交付 | 隐式修改执行状态 |

## 9. 智能体与工具设计

### 9.1 主研究智能体

职责：

- 理解用户任务、时间边界和交付格式；
- 生成可执行研究计划；
- 选择数据源和专家智能体；
- 合并去重证据；
- 判断是否需要补充检索；
- 在预算内形成结论；
- 调用引用审核；
- 生成最终报告。

主智能体不直接持有数据库凭据或任意文件系统权限。所有外部操作必须通过受控工具。

### 9.2 Web Research Agent

优先查询：

1. 官方文档和 Release Notes；
2. 论文原文、OpenReview、官方仓库；
3. GitHub Issue、Discussion 和维护者说明；
4. 可信技术博客；
5. 普通二手文章。

输出统一的 `EvidenceItem`，至少包含 URL、标题、发布者、时间、抓取时间、版本、摘要、原文片段和可信度等级。

### 9.3 Structured Data Agent

通过只读 MySQL 工具查询技术研究目录。它是研究任务的结构化证据来源，不是自然语言问数系统。工具拆分为：

- `list_sql_tables`
- `describe_table`
- `preview_table`
- `execute_readonly_query`

限制：

- 只允许单条 `SELECT` 或受控查询模板；
- 禁止 DDL、DML、多语句、注释绕过和危险函数；
- 设置行数、扫描量和超时限制；
- 返回查询摘要、列定义和截断状态；
- 保存执行 SQL 及其哈希，用于 trace 和复现。

不在本项目中实现：字段/指标语义召回、自然语言到任意 SQL、SQL 自动修正循环、业务指标语义层和复杂数据权限。这些能力会与另一个项目重复。

### 9.4 Knowledge Base Agent

职责：

- 发现可用知识库及其版本；
- 根据问题选择正确知识库；
- 执行检索并保留 chunk 级来源信息；
- 返回答案之外的原始证据片段；
- 标明检索配置、文档版本和 chunk ID。

知识库内容以一手资料为主，不将普通博客批量灌入高可信知识库。

### 9.5 File Analysis Agent

支持 PDF、Word、Excel、Markdown 和 TXT。所有文件按会话隔离，并经过：

- 扩展名、MIME 和文件头校验；
- 文件大小和页数限制；
- 安全文件名和路径规范化；
- 解析超时；
- 内容哈希去重；
- Prompt Injection 风险标记。

文件内容被视为不可信数据，不得覆盖系统策略或工具权限。

### 9.6 Citation Reviewer Agent

职责：

- 将草稿拆分为可验证声明；
- 为每条声明匹配引用；
- 检查引用片段是否蕴含声明；
- 检查版本和时间是否一致；
- 检查高风险结论是否有一手来源；
- 标记 unsupported、partial、conflict 和 stale；
- 将不合格报告退回补充研究或降级措辞。

Verifier 默认不能自主扩大研究范围，只能提出明确的证据缺口。

## 10. 数据体系

### 10.1 数据分层

| 层级 | 内容 | 更新方式 | 主要用途 |
| --- | --- | --- | --- |
| L0 固定评测快照 | 固定网页、文档、SQL 数据、PDF | 人工版本化 | 离线回归和策略对照 |
| L1 官方知识库 | 官方文档、论文、迁移指南 | 定期同步并生成版本 | RAGFlow 检索 |
| L2 结构化目录 | 框架、版本、仓库、论文、Benchmark | API/脚本同步 | SQL 分析和筛选 |
| L3 实时网络 | 最新官方网页和公开信息 | 任务运行时搜索 | 时效性研究 |
| L4 用户材料 | 上传的需求、方案和报告 | 会话级上传 | 私有约束联合分析 |

### 10.2 推荐公开数据源

- arXiv 论文与元数据；
- OpenReview 论文、版本和评审信息；
- GitHub Repository、Release、Tag、Issue 和提交元数据；
- PyPI、npm 包版本和发布时间；
- 框架官方文档、迁移指南和 Release Notes；
- 框架官方技术博客；
- 公开 Agent Benchmark 论文、数据说明和结果。

对所有来源记录：

```text
source_id
canonical_url
source_type
publisher
title
version_or_commit
published_at
retrieved_at
valid_from
valid_to
content_hash
authority_level
license
snapshot_path
```

### 10.3 MySQL 研究目录

建议表结构：

| 表 | 主要字段 |
| --- | --- |
| `frameworks` | name、vendor、license、language、homepage |
| `framework_releases` | framework_id、version、released_at、breaking_changes |
| `repositories` | framework_id、url、default_branch、latest_commit、snapshot_metrics |
| `papers` | title、arxiv_id、published_at、authors、topic、official_url |
| `benchmarks` | name、task_type、dataset_url、metric、license |
| `benchmark_results` | benchmark_id、system、version、score、source_id |
| `capability_claims` | subject、capability、value、version、source_id、confidence |
| `sources` | 统一来源元数据和版本字段 |

动态指标必须保存 `snapshot_at`，不能把当前 Star 数与历史快照混用。

### 10.4 RAGFlow 知识库划分

第一版建议建立三个知识库：

1. `agent-framework-docs`：框架官方文档、迁移指南和 Release Notes；
2. `agent-research-papers`：Agent 编排、记忆、工具使用、评测和安全论文；
3. `agent-benchmark-specs`：Benchmark 论文、任务说明、指标和限制。

每份文档必须保留版本、来源 URL、抓取时间和内容哈希。不同大版本的官方文档不得静默覆盖。

### 10.5 数据快照策略

为了使评测可复现：

- 固定评测只访问本地快照、固定 SQL dump 和固定 RAGFlow collection；
- 在线演示可以访问实时网络，但结果不计入离线基准；
- 每次评测记录数据版本、模型版本、Prompt 版本和代码 commit；
- 快照更新后生成新数据集版本，不覆盖历史评测；
- 动态来源必须显示 `as_of_date` 和 `retrieved_at`。

## 11. 领域迁移与教程兼容策略

### 11.1 基线阶段

先按教程完成：

- DeepAgents 最小示例和流式输出；
- 字典式子智能体和兼容接入；
- 中断、记忆、中间件和 Skills；
- 上下文、监控、模型和 Prompt 配置；
- Web、MySQL、RAGFlow 三个专家助手；
- 上传文件、Markdown、PDF；
- FastAPI、WebSocket 和 React 前端闭环。

基线目标是验证对教程架构的理解，不加入大规模增强。

### 11.2 最终领域版本

完成基线 tag 后，将主分支迁移为 AI Agent 技术研究领域：

- 教程 MySQL 演示数据替换为 Agent 研究目录；
- RAGFlow 示例文档替换为官方资料和论文；
- Prompt、示例问题和报告模板改为技术决策场景；
- 保留工具契约和整体架构，减少无意义重写；
- 教程原始演示仅保留在独立 tag 或文档记录中，不混入最终产品界面。

建议里程碑 tag：

```text
v0.1-tutorial-parity
v0.2-agent-domain
v0.3-evaluation
v0.4-trustworthy-citations
v0.5-reliable-runtime
v1.0-portfolio
```

## 12. 任务生命周期与持久化

### 12.1 状态机

```text
created
  -> queued
  -> planning
  -> waiting_approval
  -> running
  -> verifying
  -> generating_report
  -> succeeded

running / verifying
  -> retry_wait
  -> running

任意非终态
  -> canceling
  -> canceled

不可恢复错误
  -> failed
```

### 12.2 核心标识

- `thread_id`：用户研究会话；
- `task_id`：一次研究任务；
- `run_id`：某次执行或恢复尝试；
- `trace_id`：跨 API、Agent 和 Tool 的链路标识；
- `step_id`：计划步骤；
- `tool_call_id`：工具调用；
- `artifact_id`：报告或上传文件。

这些 ID 不得混用。

### 12.3 持久化内容

- 任务输入和配置；
- 研究计划及其版本；
- 状态转换；
- Agent 消息和工具结果摘要；
- WebSocket 事件；
- checkpoint；
- 审批请求和决策；
- Token、费用和延迟；
- 引用验证结果；
- 报告和中间 artifact 元数据。

大文件和完整网页快照放对象或文件存储，关系数据库仅保存元数据和引用。

### 12.4 恢复语义

- 服务重启后可以发现非终态任务；
- 已成功且具备幂等键的步骤不重复执行；
- 不确定是否完成的外部调用必须进入人工或补偿判断；
- WebSocket 重连可以通过 `last_event_id` 补发事件；
- 恢复执行生成新的 `run_id`，但沿用原 `task_id` 和 `trace_id` 关系；
- 恢复次数受预算和最大尝试次数限制。

## 13. 失败重试与降级

### 13.1 错误分类

| 类别 | 示例 | 默认策略 |
| --- | --- | --- |
| transient | 429、网络超时、临时 5xx | 指数退避重试 |
| permanent | 401、无权限、非法参数 | 直接失败或等待人工处理 |
| policy | SQL 越权、预算超限 | 阻止执行并记录 |
| data | 文档损坏、解析失败 | 降级或跳过并标明缺失 |
| model | 非法结构化输出、工具参数错误 | 有限修复重试 |
| verification | 引用不支持声明 | 补充检索或降级结论 |

### 13.2 重试约束

- 只对可判定的 transient 错误自动重试；
- 使用带抖动的指数退避；
- 每个工具定义最大尝试次数和总 deadline；
- 相同幂等键共享结果，避免重复付费调用；
- Retry 事件必须进入 trace；
- 重试不能绕过总成本和总时间预算。

### 13.3 降级路径

- 实时网络不可用：使用固定快照并标记时效性下降；
- RAGFlow 不可用：使用已有结构化目录和网络来源；
- SQL 不可用：跳过量化比较，不允许模型编造数值；
- PDF 生成失败：保留 Markdown 交付；
- Verifier 不可用：报告标记“未完成自动引用审核”，不伪装通过。

## 14. 引用可信度设计

### 14.1 声明模型

每条关键声明转换为：

```text
claim_id
claim_text
claim_type: fact | comparison | inference | recommendation
risk_level: low | medium | high
version_scope
time_scope
citation_ids[]
verification_status
verification_reason
```

### 14.2 来源可信度

建议等级：

- `A`：官方文档、代码、Release、论文原文；
- `B`：维护者说明、官方博客、Benchmark 官方页面；
- `C`：高质量第三方技术文章；
- `D`：普通聚合、论坛和无法确认作者的内容。

高风险技术结论至少需要一个 A 级来源。推荐结论可以基于多项事实和用户约束，但必须标为推断或建议。

### 14.3 验证流水线

```text
报告草稿
  -> 声明抽取
  -> 引用定位
  -> 规则检查
       - URL / source_id 是否存在
       - 版本和时间是否匹配
       - 引用片段是否为空
       - 来源等级是否满足要求
  -> 语义蕴含检查
  -> 冲突来源检查
  -> 生成验证结果
  -> 补充检索 / 降级措辞 / 通过
```

LLM Judge 只作为语义检查的一部分，不能替代确定性规则和人工抽检。

## 15. 编排策略与对照实验

### 15.1 待比较策略

| 策略 | 描述 | 目的 |
| --- | --- | --- |
| S0 Single Agent | 单 Agent 持有全部工具 | 最简单基线 |
| S1 Orchestrator-Workers | 教程式主智能体调度专家 | 验证角色隔离价值 |
| S2 Router + Workers | 确定性路由后调度专家 | 降低无效调用和成本 |
| S3 Planner-Executor-Reviewer | 计划、执行、验证三阶段 | 提升复杂任务成功率 |
| S4 Parallel Research + Reviewer | 并行收集多源证据后审核 | 降低延迟并增强交叉验证 |

最终产品不一定暴露全部策略，但评测代码必须能够通过配置切换。

### 15.2 公平比较条件

- 使用相同模型或明确记录不同模型；
- 使用相同数据快照、工具返回和评测问题；
- 固定最大 Token、费用、时间和重试预算；
- 每个随机配置运行多次；
- 同时报告平均值、分位数和失败分布；
- 不只报告质量，还报告成本与延迟。

### 15.3 消融实验

- 去掉 Citation Reviewer；
- 去掉并行执行；
- 去掉结构化 Router；
- 去掉来源可信度策略；
- 去掉 checkpoint 恢复；
- 去掉查询缓存；
- 不使用领域 Prompt。

每个消融实验都应回答“该模块解决了什么可观测问题”。

## 16. 评测体系

### 16.1 评测集规模

采用逐步扩展：

1. `seed-10`：跑通数据、工具、rubric 和评分器；
2. `dev-40`：覆盖主要任务和 failure case，用于开发；
3. `portfolio-100`：最终离线评测集；
4. `hidden-20`：不参与日常 Prompt 调优，用于最终泛化检查。

数字是规划上限，不以凑数量替代标注质量。

### 16.2 样本类型

| 类型 | 建议占比 | 关键评测点 |
| --- | ---: | --- |
| 单源事实查询 | 15% | 来源选择、事实准确性 |
| 多源综合 | 25% | 任务拆解、证据合并 |
| 框架对比 | 20% | 维度覆盖、版本一致性 |
| 时效与版本 | 15% | `as_of_date`、新旧版本隔离 |
| 冲突证据 | 10% | 冲突识别、不确定性 |
| 上传文件联合分析 | 10% | 私有约束提取与联合推理 |
| 失败与恢复 | 5% | 重试、降级、恢复语义 |

### 16.3 样本结构

```yaml
id: framework-checkpoint-001
query: "..."
as_of_date: "2026-07-01"
difficulty: medium
allowed_sources: [official_docs, github_release, research_catalog]
required_facts:
  - id: fact-1
    description: "..."
required_source_ids: [source-a, source-b]
expected_route: [knowledge_base, structured_data]
forbidden_claims: []
rubric:
  factuality: 0.30
  citation_correctness: 0.25
  coverage: 0.20
  version_consistency: 0.15
  decision_quality: 0.10
```

### 16.4 核心指标

#### 任务与编排

- Task Success Rate；
- Plan Completion Rate；
- Tool Routing Accuracy / Macro-F1；
- Invalid Tool Call Rate；
- Redundant Tool Call Rate；
- Recovery Success Rate；
- Human Escalation Precision。

#### 答案与引用

- Required Fact Coverage；
- Citation Precision；
- Citation Recall；
- Citation Entailment Rate；
- Unsupported Claim Rate；
- Version Consistency Rate；
- Conflict Detection Rate。

#### 性能与成本

- 端到端 P50 / P95 延迟；
- Time to First Event；
- 每任务输入/输出 Token；
- 每成功任务平均费用；
- 工具调用次数；
- 缓存命中率；
- 重试放大系数。

### 16.5 自动评测与人工评测

- 确定性事实、路由、引用存在性和版本字段使用程序评分；
- 语义支持关系使用规则、NLI 或 LLM Judge 辅助；
- 决策质量使用明确 rubric，而不是“整体看起来不错”；
- 至少 10% 样本进行人工复核；
- 对 Judge 本身建立一致性抽检；
- 最终报告同时展示总体结果和典型失败案例。

## 17. 可观测性

### 17.1 事件模型

建议事件：

```text
task_created
task_state_changed
plan_created
plan_revised
approval_requested
approval_resolved
agent_started
agent_completed
tool_started
tool_completed
tool_failed
retry_scheduled
checkpoint_saved
task_resumed
claim_verified
budget_warning
artifact_created
task_succeeded
task_failed
```

每个事件包含：`event_id`、`timestamp`、`thread_id`、`task_id`、`run_id`、`trace_id`、`actor`、`type`、`payload_version` 和脱敏后的 `payload`。

### 17.2 Trace

层级建议：

```text
research_task span
  ├── planning span
  ├── subagent span
  │     └── tool span
  ├── synthesis span
  ├── citation_review span
  └── report_generation span
```

必须能够回答：

- 某个结论来自哪次工具调用；
- 某次失败为什么触发重试或降级；
- 哪个阶段消耗了最多 Token 和时间；
- 某次恢复从哪个 checkpoint 开始；
- 某条引用为什么未通过。

### 17.3 日志和指标

- 使用结构化 JSON 日志；
- 对密钥、Cookie、文件内容和模型上下文做脱敏；
- 暴露任务、错误、延迟、Token、费用、重试和队列指标；
- 前端事件流用于用户体验，不能替代后端持久化事件和 telemetry；
- 可选接入 OpenTelemetry 和本地可视化后端，避免核心逻辑依赖商业平台。

## 18. 人工审批

### 18.1 审批点

第一版只设置三个高价值审批点：

1. **计划审批**：高成本或高复杂度任务执行前确认计划与预算；
2. **风险工具审批**：超出普通只读范围、访问上传敏感材料或触发高额调用前确认；
3. **报告发布审批**：存在部分支持、来源冲突或高风险建议时确认是否发布。

### 18.2 审批契约

审批请求包含：

- 即将执行的动作；
- 原因和预期收益；
- 预计成本与时间；
- 涉及的数据源；
- 风险；
- `approve`、`reject`、`edit` 选项；
- 审批超时后的默认行为。

审批必须持久化，恢复后不能重复询问已决策的同一动作。

## 19. Token 与成本治理

### 19.1 预算维度

- 最大总 Token；
- 最大模型费用；
- 最大工具费用；
- 最大墙钟时间；
- 最大规划迭代次数；
- 最大子智能体调用次数；
- 最大并发数；
- 最大检索轮数。

### 19.2 治理策略

- 路由、分类和简单抽取优先使用低成本模型；
- 高价值综合和验证按需使用更强模型；
- 缓存相同数据版本下的检索和工具结果；
- 对上下文去重和压缩，但保留引用定位；
- 达到 70%、90% 预算时发出事件；
- 超预算前进入降级或审批，不允许无限执行；
- 报告展示实际 Token、费用、工具次数和耗时。

## 20. API 与实时协议

### 20.1 建议 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/tasks` | 创建研究任务 |
| GET | `/api/tasks/{task_id}` | 查询任务状态和摘要 |
| POST | `/api/tasks/{task_id}/cancel` | 取消任务 |
| POST | `/api/tasks/{task_id}/resume` | 恢复任务 |
| GET | `/api/tasks/{task_id}/events` | 分页读取历史事件 |
| WS | `/ws/tasks/{task_id}` | 实时事件流和断线续传 |
| POST | `/api/uploads` | 上传会话文件 |
| GET | `/api/artifacts` | 查询任务产物 |
| GET | `/api/artifacts/{artifact_id}/download` | 下载产物 |
| GET | `/api/approvals` | 查询待审批事项 |
| POST | `/api/approvals/{approval_id}` | 提交审批决策 |
| POST | `/api/evaluations/runs` | 启动离线评测 |
| GET | `/api/evaluations/runs/{run_id}` | 查询评测结果 |

### 20.2 WebSocket 可靠性

- 事件拥有单调递增 `event_id`；
- 客户端重连时携带 `last_event_id`；
- 服务端先补发历史事件，再切换到实时事件；
- 心跳与业务事件分离；
- 慢客户端有缓冲和断开策略；
- WebSocket 断开不取消后端任务。

## 21. 前端范围

前端是研究任务工作台，不做营销落地页。第一版包含：

- 任务输入和示例任务；
- 文件上传；
- 数据快照、编排策略和预算配置；
- 计划步骤和当前状态；
- Agent 与工具事件流；
- 证据列表和来源等级；
- 引用检查结果；
- 审批面板；
- Token、成本、耗时和工具调用统计；
- Markdown 报告预览；
- Markdown/PDF 下载；
- 失败、重试、取消和恢复入口。

前端不直接解析 Agent 内部消息作为状态来源，应消费版本化事件契约。

## 22. 安全与治理

### 22.1 Prompt Injection

- 网页、PDF、文档和数据库文本均为不可信数据；
- 系统提示与来源内容在消息结构中隔离；
- 来源中的“忽略指令”“调用工具”等内容只能作为引用文本；
- 检测可疑指令并记录安全事件；
- 子智能体不能通过来源内容扩大权限。

### 22.2 Web 安全

- 限制允许的 URL scheme；
- 阻止 localhost、私网、metadata endpoint 和 DNS rebinding；
- 设置下载大小、超时和重定向次数；
- 解析 HTML 时移除活动脚本；
- 遵守 robots、站点条款和授权边界。

### 22.3 SQL 安全

- 独立只读数据库账号；
- 语法树或数据库权限双重限制；
- 查询超时、最大行数和资源限制；
- 禁止跨库访问、文件函数和多语句；
- 对敏感列配置显式 denylist。

### 22.4 文件安全

- 防路径穿越和文件覆盖；
- 上传目录与输出目录分离；
- 限制格式、大小、页数和压缩包；
- 文件名不作为可信标识；
- 生成文件使用服务器分配的 artifact ID。

## 23. 测试策略

### 23.1 单元测试

- 状态转换；
- Prompt 和配置加载；
- 路由策略；
- SQL 安全校验；
- 文件路径和 MIME 校验；
- 预算计算；
- 重试分类；
- 引用规则；
- 事件序列化；
- 成本计算。

### 23.2 集成测试

- Agent 与 mock 工具；
- MySQL 查询；
- RAGFlow 适配器；
- 任务持久化和 checkpoint；
- WebSocket 断线补发；
- 上传、解析和 artifact 下载；
- 审批暂停与恢复；
- Markdown/PDF 生成。

### 23.3 端到端测试

- 网络搜索任务；
- SQL + RAG 跨源任务；
- 上传文件联合分析；
- 引用验证失败后补充研究；
- 服务重启后的任务恢复；
- 用户取消任务；
- 预算耗尽后的降级；
- 人工拒绝计划后的终止。

### 23.4 故障注入

- 模型超时或返回非法结构；
- Tavily 429/500；
- MySQL 断连；
- RAGFlow 超时；
- WebSocket 断开；
- 进程在步骤中途终止；
- checkpoint 写入失败；
- PDF 转换失败；
- 引用来源被删除或版本不匹配。

## 24. 实施路线

### Phase 0：仓库和执行纪律

交付物：

- 项目 README、架构决策记录和开发规范；
- Python、Node、Docker 环境；
- `.env.example` 和密钥扫描；
- 后端/前端测试骨架；
- CI 基线；
- 教程来源和实现边界说明。

验收：空项目可以安装、测试、构建，密钥不进入 Git。

### Phase 1：DeepAgents 能力铺垫

对应教程前置章节：

- invoke、stream 和 chunk；
- 字典式子智能体；
- LangGraph/Runnable 兼容；
- interrupt、审批和恢复；
- backend、store、memory；
- middleware 和 skills。

验收：每个概念都有最小示例、测试或学习记录，能解释其用途和限制。

### Phase 2：教程项目基线

实现：

- context、monitor、LLM、Prompt 配置；
- Web、MySQL、RAGFlow 子智能体；
- 主智能体；
- 文件读取和报告生成；
- FastAPI、WebSocket 和 React 页面；
- 会话隔离、任务取消、文件下载。

验收：完成教程核心演示，并打 `v0.1-tutorial-parity` tag。

### Phase 3：AI Agent 领域迁移与评测基线

实现：

- MySQL Agent 研究目录；
- RAGFlow 官方资料和论文知识库；
- 固定 Web 快照；
- `seed-10` 和 `dev-40`；
- S0/S1 两种策略；
- 基础评测 runner 和结果报告。

验收：离线环境可重复运行，结果绑定数据、模型、Prompt 和代码版本。

### Phase 4：引用可信度

实现：

- `EvidenceItem` 和 `Claim` 模型；
- 来源等级；
- 声明抽取；
- 规则检查；
- 语义支持检查；
- 冲突和过期来源标记；
- 前端引用面板。

验收：评测报告包含 Citation Precision、Recall、Entailment 和 Unsupported Claim Rate。

### Phase 5：编排策略对照

实现 S2-S4、统一策略接口、并行控制和消融开关。

验收：在相同预算和数据上比较质量、成本、延迟与失败类型，明确最终默认策略。

### Phase 6：全链路可观测性

实现：

- 版本化事件模型；
- 结构化日志；
- trace/span；
- 指标和本地 dashboard；
- 前端运行详情。

验收：可从最终声明追溯到 Agent、工具、来源和成本。

### Phase 7：持久化和恢复

实现：

- 任务状态机；
- task/event/checkpoint 存储；
- 幂等键；
- 自动重试和降级；
- 服务重启恢复；
- WebSocket 事件续传。

验收：故障注入后可恢复的任务达到预设恢复语义，且无重复副作用。

### Phase 8：人工审批和成本治理

实现计划、风险工具和报告发布审批，以及 Token、费用、时间、工具和并发预算。

验收：审批可暂停并跨重启恢复；任务不会突破硬预算静默继续。

### Phase 9：作品集发布

实现：

- `portfolio-100` 和 `hidden-20`；
- 最终实验报告；
- 3 个高质量演示案例；
- failure case 复盘；
- Docker Compose 一键启动；
- 架构图、演示视频和完整 README；
- 简历 STAR 与面试问答。

验收：陌生读者可以独立启动、运行演示、理解指标并复现主要实验。

### 24.1 Phase Gate 与范围冻结

每个阶段只能在前一阶段通过验收后开始。特别是：

- Phase 2 只证明教程基线可运行，不提前实现生产化能力；
- Phase 3 只完成领域数据、固定快照和评测 runner，不同时建设所有 AgentOps；
- Phase 4-5 优先证明引用和编排是否有效，若实验没有收益，应删除对应复杂度；
- Phase 7-8 只围绕长任务可靠性和人工治理，不复制 Text-to-SQL 项目的 SQL 语义层；
- Phase 9 前必须冻结功能范围，只修复阻塞发布的问题。

任何新增功能必须回答三个问题：它解决哪个已观察 failure case？如何测量收益？为什么不属于另一个项目？无法回答时进入 backlog，不进入当前版本。

## 25. 复杂度与时间判断

### 25.1 难度

| 阶段 | 难度 | 主要风险 |
| --- | ---: | --- |
| 教程能力铺垫 | 4/10 | 框架 API 和版本变化 |
| 教程基线 | 6/10 | 多服务配置和异步联调 |
| 领域数据与评测 | 7/10 | 标注质量和可复现性 |
| 引用验证 | 8/10 | 声明拆分和语义支持判断 |
| 编排实验 | 8/10 | 公平比较和随机性 |
| 持久化恢复 | 9/10 | 幂等性、事件顺序和恢复语义 |
| 人工审批与成本治理 | 8/10 | 状态一致性和策略边界 |

### 25.2 粗略工作量

在不限制总周期、以质量优先的前提下：

- 教程学习与基线：50-80 小时；
- 领域迁移和数据：40-70 小时；
- 评测与引用验证：60-100 小时；
- 可观测性和可靠执行：60-100 小时；
- 审批、成本、前端和发布：50-80 小时；
- 总计：约 260-430 小时。

该估算不包含大规模手工数据标注和外部服务部署故障带来的额外时间。

## 26. 主要风险与应对

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 框架快速变化 | 教程代码失效 | 锁定版本、记录迁移、适配器隔离 |
| 数据动态变化 | 评测不可复现 | 固定快照、版本号和内容哈希 |
| Agent 随机性 | 实验结果波动 | 多次运行、固定预算、报告分布 |
| LLM Judge 偏差 | 评分不可信 | 确定性规则、人工抽检、多 Judge 对照 |
| 多智能体没有收益 | 架构显得过度设计 | 保留简单基线，用实验决定默认策略 |
| 外部 API 不稳定 | 演示失败 | mock、缓存、快照、降级和熔断 |
| 功能膨胀 | 长期无法交付 | 严格 Phase gate，不并行开启后续阶段 |
| 数据授权问题 | 无法公开发布 | 记录 license，只收录可用资料或元数据 |
| Prompt Injection | 工具越权或错误结论 | 内容隔离、最小权限、审批和安全测试 |
| 指标被过度包装 | 面试追问失败 | 保存原始评测记录，只写可复现数字 |

## 27. 开源、署名与原创性

该项目以公开教程和配套仓库作为学习参考，应在 README 中明确致谢和链接。

截至本规划调研时，上游仓库根目录未观察到明确的 `LICENSE` 文件。没有许可证不等于可以复制并重新发布。因此：

- 不直接复制大段上游代码作为自己的作品；
- 根据教程理解独立实现，并保留自己的提交历史；
- 对不可避免的少量引用标明来源；
- 发布前再次确认上游许可证或取得作者许可；
- 在 README 中区分“教程基线能力”和“独立增强能力”；
- 简历只描述本人实际设计、实现和验证的部分。

## 28. Definition of Done

项目达到简历可用标准，必须同时满足：

- [ ] 教程核心链路完整运行；
- [ ] 最终领域统一为 AI Agent 技术研究；
- [ ] Web、SQL、RAG 和文件四类数据源可用；
- [ ] 至少三种编排策略可配置比较；
- [ ] 有版本化固定评测集和独立隐藏集；
- [ ] 有真实的质量、成本、延迟和恢复指标；
- [ ] 关键声明具有可定位引用和验证状态；
- [ ] 任务、事件和 checkpoint 持久化；
- [ ] 服务重启、API 失败和断线场景经过故障测试；
- [ ] 人工审批可以暂停、修改、拒绝和恢复；
- [ ] Token 和费用硬预算生效；
- [ ] 日志脱敏，SQL、Web 和文件工具具备安全边界；
- [ ] 后端、前端、集成和端到端测试通过；
- [ ] Docker Compose 可以启动完整演示环境；
- [ ] README、架构图、评测报告、failure case 和演示视频齐全；
- [ ] 所有简历数字均可由仓库中的命令复现。
- [ ] Structured Data Agent 没有演变成第二套自然语言问数或指标语义层。
- [ ] 简历中使用的核心指标与 Shopkeeper Analytics 不重复。

## 29. 简历 STAR 草案

> 以下内容是最终写法模板，不得在尚未实现和评测前填写虚构数字。

### Situation

AI Agent 框架的能力信息分散在官方文档、论文、GitHub、Benchmark 和版本记录中，普通搜索或单次 RAG 难以完成跨来源核验，也无法稳定处理长任务、引用一致性和中断恢复。

### Task

设计并实现一个面向 Agent 框架选型和技术决策的多智能体可信研究系统，使其能够动态调用多类数据源、生成可追溯报告，并通过固定评测集验证不同编排策略的质量、成本和可靠性。

### Action

可拆成 3-4 条简历 bullet：

- 基于 DeepAgents、LangGraph 与 FastAPI 设计 Planner-Executor-Reviewer 多智能体架构，统一封装网络搜索、只读 SQL、RAGFlow 和文件分析工具，并通过版本化事件协议向 React 前端实时推送计划、执行和验证状态。
- 构建声明级引用验证流水线，对报告进行 Claim 抽取、来源分级、版本一致性和语义支持检查，将不受支持声明自动退回补充检索或降级措辞。
- 实现任务、事件与 checkpoint 持久化，通过幂等键、错误分类、指数退避、断线续传和服务重启恢复保障长任务执行，并加入计划/风险工具/报告发布三类人工审批。
- 建立固定数据快照和 Agent 评测集，对 Single Agent、Orchestrator-Workers、Router-Workers 和 Planner-Executor-Reviewer 进行消融实验，统一统计任务成功率、工具路由、引用质量、P95 延迟、Token 和费用。

### Result

完成后按真实结果填写：

- 在 `[样本数]` 条隐藏评测集上，默认策略相较 Single Agent 将任务成功率由 `[A]%` 提升至 `[B]%`；
- Citation Precision 达到 `[C]%`，Unsupported Claim Rate 降至 `[D]%`；
- 在质量不下降的前提下，平均 Token 或费用下降 `[E]%`；
- 故障注入测试中，`[F]/[G]` 个可恢复任务在进程重启后成功续跑；
- P95 延迟为 `[H]`，无效工具调用率为 `[I]%`。

### 简历压缩版模板

```text
Agent Engineering Research Copilot｜多智能体可信技术研究系统
技术栈：Python、DeepAgents、LangGraph、FastAPI、WebSocket、MySQL、RAGFlow、React、Docker

- 设计 Planner-Executor-Reviewer 多智能体架构，动态调度 Web、SQL、RAG 和文件分析能力，支持长任务流式执行、取消、持久化 checkpoint 及服务重启恢复。
- 构建声明级引用验证与来源分级机制，在 [N] 条固定评测集上将 Citation Precision 提升至 [X]%，Unsupported Claim Rate 降至 [Y]%。
- 对 [策略列表] 开展编排消融实验，以任务成功率、工具路由准确率、P95 延迟和单任务成本选择默认策略，使 [核心指标] 改善 [Z]%。
- 实现 Token/费用预算、错误分类重试、WebSocket 断线续传和人工审批，故障注入场景下任务恢复成功率达到 [R]%。
```

## 30. 面试证据清单

最终仓库应能直接回答：

1. 为什么这里需要 Agent，而不是固定工作流？
2. 为什么需要多个 Agent，Single Agent 的实验结果是什么？
3. 为什么使用 DeepAgents，LangGraph 在底层承担什么职责？
4. 如何防止主智能体错误路由或无限委派？
5. checkpoint 保存什么，恢复时如何避免重复副作用？
6. WebSocket 断开为什么不会导致任务丢失？
7. 如何证明一条引用真正支持对应声明？
8. LLM Judge 不稳定时，评测结果为什么仍然可信？
9. 动态网络数据如何保证实验可复现？
10. SQL Agent 如何防止越权和危险查询？
11. Prompt Injection 如何跨网页、RAG 和文件传播，系统如何阻断？
12. 多智能体带来的成本和延迟如何量化？
13. 哪个增强功能实验后没有收益，为什么保留或删除？
14. 任务恢复的语义是 at-most-once、at-least-once 还是 effectively-once？
15. 哪些指标可以自动计算，哪些必须人工判断？
16. 为什么这个项目不把数据库查询做成通用 Text-to-SQL？
17. 两个项目分别解决什么问题，为什么不能合并成一个系统？

每个问题都应链接到代码、测试、ADR、评测结果或 failure case，而不是只准备口头答案。

## 31. 待实施前确认的决策

以下决策不影响当前规划成立，但应在对应 Phase 开始前通过 ADR 固化：

1. 最终模型供应商及低成本/高质量模型分工；
2. 任务和 checkpoint 持久化选择 SQLite、PostgreSQL 或框架原生方案；
3. telemetry 使用纯 OpenTelemetry 还是增加 Langfuse/LangSmith；
4. RAGFlow 是否保留为最终知识库，还是在对照实验后替换；
5. 固定网页快照的存储格式和授权策略；
6. Citation Verifier 使用的 NLI/LLM Judge 组合；
7. 默认编排策略，由 Phase 5 的实验结果决定；
8. 线上演示是否允许实时 Web 搜索，或仅开放受控快照模式。

## 32. 下一步

1. 审阅并确认本文档的目标、非目标和 Phase 顺序；
2. 确认上游教程代码的许可证和可复用边界；
3. 为 Phase 0-2 编写逐任务实施计划；
4. 建立空仓库、CI 和最小测试骨架；
5. 按教程章节推进，每个阶段独立验收，不提前混入后续增强。
6. 先冻结本项目与 Shopkeeper Analytics 的边界，再开始 Phase 0 实现。

## 附录 A：参考入口

### 教程与基线源码

- 教程：[AI 智能体实战速成指南 - 深度研搜](https://didilili.github.io/ai-agents-from-zero/#/%E5%AE%9E%E6%88%98%E9%A1%B9%E7%9B%AE-%E6%B7%B1%E5%BA%A6%E7%A0%94%E6%90%9C/0-%E5%89%8D%E8%A8%80)
- 配套源码：[didilili/deepsearch-agents](https://github.com/didilili/deepsearch-agents)
- 教程源码：[didilili/ai-agents-from-zero](https://github.com/didilili/ai-agents-from-zero)

### 候选一手数据源

- 论文：[arXiv](https://arxiv.org/)
- 论文与评审：[OpenReview](https://openreview.net/)
- 开源项目元数据：[GitHub REST API](https://docs.github.com/en/rest)
- Python 包版本：[PyPI](https://pypi.org/)
- Node.js 包版本：[npm](https://www.npmjs.com/)
- 公开数据集与 Benchmark：[Hugging Face Datasets](https://huggingface.co/datasets)

实际纳入数据集前，必须逐项记录许可证、抓取时间、版本、内容哈希和允许的再分发范围。本附录只提供候选入口，不代表所有页面或数据都可直接复制、缓存或公开发布。
