# deepsearch-agents

多轮对话研究助手：每轮回答组合本地知识库（Qdrant）、实时网络（Tavily，逐轮开关）与会话上传文件三类证据，产出带引用编号、可追溯出处的回答。

## 架构

每回合是一条 LangGraph 固定 DAG 流水线：

```
plan ──► retrieve ──► review ◄──┐
                        │       │ 补充检索回环
                 (有新查询且预算内) │ 轮次≤3 / 总查询≤6
                        ▼       │
                  supplemental ─┘
                        │ (收敛或预算耗尽)
                        ▼
                   synthesize ──► END
```

- **plan**：规划器一次模型调用，拆解子问题并生成知识库/网络查询；输出 `research_intensity` 与 `search_hints`（缺失时回退关键词启发），当前日期自动注入提示词。
- **retrieve**：三类证据源并行检索。knowledge 透传 Qdrant 融合分（批级归一到 [0,1]）；web/session_file 按命中位次给衰减分。
- **review**：覆盖审阅器逐子问题判定 covered/partial/uncovered，生成补充查询——每个回合都会执行，无跳过捷径。
- **supplemental**：跨轮记账的有界补充检索；预算耗尽仍有缺口时记入 limitations 而非死循环。
- **synthesize**：综合器按全局分数排序的证据撰写带 claims/引用编号的回答；`ENABLE_CITATION_VALIDATION=true` 时逐 claim 过 app/citations 规则引擎，未获支持的陈述被裁剪并记入 limitations。

多轮上下文：最近 6 回合 / 12000 字符的对话历史注入规划器、审阅器与综合器三者。

## 快速开始

```bash
uv sync --extra dev             # 或 python -m venv .venv && pip install -e .[dev]
cp .env.example .env            # 填入 MODEL_API_KEY 等真实密钥
uv run --extra dev python -m pytest -q   # 全量测试（integration 无外部依赖可直接跑）
ruff check app tests benchmarks scripts
```

知识库重建（首次运行需要）：

```bash
python scripts/index_knowledge.py        # 从 data/knowledge 语料构建 Qdrant 本地索引
```

启动：FastAPI + WebSocket 入口在 `app/api/server.py`（`uvicorn app.api.server:app`）；前端在 `frontend/` 下 `pnpm install && pnpm dev`。

## 配置

模型走 OpenAI 兼容协议（默认 `openai:gpt-4.1-mini`），全部键见 `.env.example`，常用的：

| 键 | 默认 | 说明 |
|---|---|---|
| MODEL_NAME / MODEL_BASE_URL / MODEL_API_KEY | — | 模型与端点 |
| MODEL_TEMPERATURE | 0.2 | 未设置时跟随 provider 默认 |
| MODEL_MAX_RETRIES | 2 | 瞬时抖动重试 |
| ENABLE_CITATION_VALIDATION | false | 引用校验规则引擎开关 |
| TAVILY_API_KEY | — | 不设则 web 检索不可用（fail-closed） |

## 测试

- 单测集中在 `tests/unit`，契约式风格；integration 在 `tests/integration`（本机无需 qdrant/tavily 服务即可运行）。
- 评测框架 s0/s1 策略与数据集在 `benchmarks/evaluation`（独立于运行链路），入口 `scripts/evaluate.py`。

## 项目状态

原仓库的清理与智能化改进（去冗余 A1-A4、优化 B1-B9）已在本工作区完成，任务明细与执行记录见 [EXECUTION_LOG.md](EXECUTION_LOG.md)；历史文档保留在原仓库 `/Users/wxhu/Documents/reasonix/deepsearch-agents`。
