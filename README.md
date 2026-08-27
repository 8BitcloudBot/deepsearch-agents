# deepsearch-agents（干净基线副本）

多轮对话研究助手：每轮回答组合本地知识库（Qdrant）、实时网络（Tavily，逐轮开关）与会话上传文件三类证据，产出带引用编号的回答。

> 本目录是从原仓库 `/Users/wxhu/Documents/reasonix/deepsearch-agents` 选择性迁移的**改造工作区**。原仓库保持只读不动；运行时产物（.env、.data、output/、updated/、venv、node_modules）与历史文档未随迁。

## 当前状态

- 代码功能与原仓库完全一致（基线），智能化改进尚未开始。
- 改造任务手册：《deepsearch-agents-改进计划.md》；执行流程指令：《deepsearch-agents-执行提示词.md》。
- 执行进度记录在 `EXECUTION_LOG.md`（由执行会话创建与维护）。
- 原仓库的历史文档（ADR、阶段交接、验收记录等）归档在 `benchmarks/docs-history/`。

## 快速开始

```bash
uv sync                        # 或 python -m venv .venv && pip install -e .[dev]
cp .env.example .env           # 填入 MODEL_API_KEY 等（本目录不含真实密钥）
python -m pytest -q            # 单测
ruff check app
```

知识库重建（首次运行需要）：

```bash
python scripts/index_knowledge.py        # 从 data/knowledge 语料构建 Qdrant 本地索引
```

启动：uvicorn 入口见 `app/api/server.py`；前端在 `frontend/` 下 pnpm install && dev。
