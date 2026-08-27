# 项目指令（AGENTS.md）

本文件由 ZCode 自动加载。请遵守其中约定。

## 项目一句话

多轮对话研究助手：每轮回答组合本地知识库（Qdrant）、实时网络（Tavily）、会话上传文件三类证据，产出带引用编号的回答。固定 DAG 流水线，补充检索为带预算的多轮回环（≤3 轮 / 总查询 ≤6）。改造任务 A1-A4、B1-B9 已完成并合入 main（见 `EXECUTION_LOG.md`）；原仓库 `/Users/wxhu/Documents/reasonix/deepsearch-agents` 只读不动，其 `.data/knowledge-corpus/beginner-v2/manifest.json` 是知识索引的分块清单来源。

## 每次会话开始时

1. 若存在 `EXECUTION_LOG.md` → 先读它，那是改造进度的唯一真源；从"进行中"条目恢复，禁止重做已完成任务。
2. 找不到要做什么时：任务手册《deepsearch-agents-改进计划.md》，阶段流程《deepsearch-agents-执行提示词.md》。
3. 历史文档**未随迁本工作区**（原样保留在 `/Users/wxhu/Documents/reasonix/deepsearch-agents`）。需要查证历史背景时去原仓库目录找，不要在垃圾箱或 reflog 里恢复已删内容。

## 常用命令

```bash
python -m pytest -q                # 单测（integration 用标记分层，按 pyproject 实际配置）
ruff check app                     # lint
python scripts/index_knowledge.py  # 从 data/knowledge 重建 Qdrant 本地索引
# 服务入口：app/api/server.py（FastAPI + WebSocket）；前端在 frontend/ 下 pnpm install && dev
```

`.env` 已就位且含真实密钥：**绝不提交、绝不在回复里原文打印密钥值**。

## 代码地图

| 路径 | 职责 |
|---|---|
| `app/conversation/turn.py` | 回合研究引擎，LangGraph 固定 DAG 本体 + 规模常量区（顶部） |
| `app/conversation/runtime.py` | 三角色模型适配器（规划器 / 覆盖审阅器 / 综合器）+ 三类证据检索器 |
| `app/conversation/contracts.py` | TurnResearchPlan / EvidenceItem（含 score）/ SynthesisDraft 等数据合同 |
| `app/conversation/output_schemas.py` | B2 模型输出 Pydantic 合同桥（校验失败原样透传旧行为） |
| `app/conversation/heuristics.py` | 共享轻量助手（is_deep_request 回退 / rank_decay_scores） |
| `app/conversation/application.py`、`store.py`、`settings.py`、`model.py` | 编排入口 / SQLite 状态机 / 配置 / 模型构造与错误分类 |
| `app/knowledge/`、`app/providers/tavily.py`、`app/tools/files.py` | 知识库混合检索 / Web 检索 / 附件解析 |
| `app/citations/runtime_adapter.py` | 引用校验运行时适配层（ENABLE_CITATION_VALIDATION 控制，默认关；rules 为英文词法设计，中文语料系统性误杀——见 EXECUTION_LOG 验证结论） |
| `benchmarks/evaluation/` | 评测框架 s0/s1 策略与数据集（独立于运行链路），入口 scripts/evaluate.py |

关键开关（`.env`）：`ENABLE_CITATION_VALIDATION`（默认 false）、`MODEL_STRUCTURED_OUTPUT`（默认 false，全角色 json_object 强约束）、`MODEL_TEMPERATURE/MODEL_MAX_RETRIES/MODEL_TOP_P`（默认 0.2/2/None）。

## 红线（任何任务不得削弱）

1. fail-closed 安全姿态：web 开关关闭强制 web_queries 为空；附件按 user/conversation 隔离；敏感信息脱敏。
2. `store.py` 的回合状态机与存储合同不得变更语义。
3. 错误脱敏走 `model.py` 的稳定枚举文案。
4. `app/citations` 包不删除、不改其规则语义。
5. API/WS 响应合同向后兼容。

## 工作纪律

- 一律中文回复。计划书里的 文件:行号 是快照——**动手前先 grep 定位标识符确认**，对不上就停下报告。
- 当前分支基线是 `main`；改造提交在 `opt/deepsearch` 分支上做（已存在则继续用）。一个任务一个 commit（message 以任务编号开头），**测试全绿才提交**，只做本地提交不推送。
- 会话每轮结尾输出三行：【已完成】【测试状态】【下一步】。

## 验证策略（沿用原仓库的有效原则）

选能证明本次行为变化的最小测试面：局部改动跑最近归属边界的聚焦测试；跨模块合同改动补对应契约测试；完整套件留给里程碑验收。不要每次小编辑都跑全套，也不要把同一断言复制多层。
