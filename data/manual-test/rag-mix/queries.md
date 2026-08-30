# RAG 混合分库查询集与轮换剧本（暂不执行——供执行会话使用）

> 构建日期 2026-08-30。文档来源与整理日期见各文件头部。
> 判据约定：`[G]` = 预期证据来自全局库（主语料），`[P]` = 个人库，`[G+P]` = 两者；
> "必含" = 回答正文必须出现的关键事实词（召回判据）；每条另列"证据源检查"。

## 一、单条问询——单独知识（6 条）

| # | 问题 | 预期 | 必含 | 证据源检查 |
|---|---|---|---|---|
| S1 | Pi agent 的设计哲学是什么？它刻意不内置哪些能力？ | [G] | 极简 / minimal；MCP、sub-agents（至少其一）；扩展自建 | evidence 含 pi-agent-overview |
| S2 | Codex CLI 是用什么语言实现的？如何安装？ | [G] | Rust（codex-rs）；curl -fsSL …/install.sh 或 npm install -g @openai/codex | evidence 含 codex-harness-overview |
| S3 | DeepSeek Harness 的四种运行模式分别是什么？ | [G] | Standard / Code / Minimal / Creator | evidence 含 deepseek-harness-overview |
| S4 | RagFlow 的核心特性有哪些？自托管需要什么硬件条件？ | [G] | 模板化分块 或 deepdoc；CPU 4 核 / RAM 16GB（至少其一） | evidence 含 ragflow-overview |
| S5 | Pi 的树状 session 管理和 steering 机制是怎么工作的？ | [P] | /tree 分叉；Enter 打断 / Alt+Enter 排队 | evidence 来自个人库文档 |
| S6 | RagFlow 对 DeepSeek v4 的支持是什么时候加入的？之前还支持了哪些模型？ | [P] | 2026-04-24；GPT-5（2025-08-08）或 Gemini 3 Pro | evidence 来自 ragflow-notes |

## 二、单条问询——交叉知识（3 条）

| # | 问题 | 预期 | 必含 | 证据源检查 |
|---|---|---|---|---|
| X1 | pi、Codex、DeepSeek Harness 三个编码 agent harness 的扩展/插件机制有什么不同？ | [G+P] | pi=TS 扩展+skills；codex=MCP（codex mcp）；dsh=Cordis 全插件 | evidence 同时出现两类以上文档 |
| X2 | RAGFlow 2026-04-24 支持 DeepSeek v4——这与 DeepSeek Harness 是什么关系？V4 模型能被哪些系统使用？ | [G+P] | ragflow 时间线；dsh 定位（运行时/model-plus-runtime）；pi 的 15+ providers 作为对照 | 跨库 evidence |
| X3 | 这四个系统（pi / Codex / DeepSeek Harness / RagFlow）各自的会话或运行记录可追溯性是如何实现的？ | [G+P] | dsh=append-only session log / Trajectory；pi=树状 session 单文件；其余允许以 limitations 表达证据不足 | dsh 个人或全局文档命中 |

## 三、单会话轮换剧本（2 / 3 / 4 轮）

### 剧本 R2（2 轮，单库内递进）

1. [G] "Codex CLI 是什么？核心用什么语言实现？" （必含 Rust / terminal coding agent）
2. [G] "它的 MCP 支持怎么用？" （承接第 1 轮主语 Codex；必含 codex mcp；验证 recent_history 不重问第 1 轮已答内容）

### 剧本 R3（3 轮，跨库轮换）

1. [P] "RAGFlow 的更新时间线上有哪些 2026 年的节点？" （必含 2026-06-15 多渠道 或 2026-04-24 DeepSeek v4）
2. [G] "那 RagFlow 的核心检索特性是什么？" （换到全局库；必含 模板化分块 或 融合重排）
3. [G+P] "它 2026-04-24 支持的 DeepSeek v4，在当时意味着什么？结合 RAGFlow 生态说说。" （交叉第 1/2 轮；验证跨库召回与承接）

### 剧本 R4（4 轮，三库主题轮换+总结）

1. [G] "DeepSeek Harness 是什么？有哪些运行模式？" （必含 Cordis / Standard / Minimal）
2. [P] "DeepSeek Harness 的 Agent = Model + Harness 公式和 Trajectory 视图是什么？" （个人库；必含 公式 / append-only）
3. [G] "pi agent 与 Codex CLI 在扩展机制上分别是怎么做的？" （换到另两主题；必含 TS 扩展/skills、codex mcp）
4. [G+P] "综合前面聊到的 harness（pi、Codex、DeepSeek Harness）与 RagFlow：一个 RAG 引擎与 agent harness 生态如何互相配合？" （四主题总结；验证跨库召回 + 多轮承接；允许 limitations 表达证据不足处）

## 四、评测口径

- **召回判据**：回答正文含"必含"词（宽松匹配）；evidence 列表中出现预期文档标题/document_id
- **跨库召回**：单回合 evidence 中同时出现主库（ragmix-*）与个人库（upload-*）来源
- **记录项**：耗时、首字（流式开）、partials 数、claims/limitations 数、evidence 来源分布
- **已知噪音**：主库内含 134 chunks 冻结语料（LangGraph/Qdrant 等）——S1/X1 等查询时冻结语料可能同场竞争，这本身是观察点（跨主题干扰）
- **脚本**：入库 `ingest.py`（幂等）；回归执行可基于 scripts/regression_e2e.py 扩展轮换剧本
