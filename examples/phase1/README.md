# Phase 1 DeepAgents Capability Examples

> **Historical background:** The Phase 1 README records the tutorial-era
> Phase 2 preview vocabulary only. It is not current product or execution
> guidance; current direction is defined by `docs/phase-status.md`.

七个独立、可运行的 DeepAgents 能力示例。

## 示例映射

| # | Name | File | Concept |
|---|------|------|---------|
| 1 | invoke | `01_invoke.py` | 基本 agent 调用 |
| 2 | stream | `02_stream_chunks.py` | 流式输出与事件标准化 |
| 3 | dictionary-subagents | `03_dictionary_subagents.py` | TypedDict 声明式子智能体 |
| 4 | runnable-subagent | `04_runnable_subagent.py` | LangGraph Runnable 子智能体 |
| 5 | interrupt-resume | `05_interrupt_resume.py` | interrupt / 审批 / resume |
| 6 | backend-store-memory | `06_backend_store_memory.py` | Backend / Store / Memory |
| 7 | middleware-skills | `07_middleware_skills.py` | Middleware 与 Skills |

## 运行命令

### 列出所有示例

```bash
.venv/bin/python -m examples.phase1.runner --list
```

### 运行单个示例（需要 MODEL_API_KEY）

```bash
MODEL_API_KEY=sk-... .venv/bin/python -m examples.phase1.runner invoke
MODEL_API_KEY=sk-... .venv/bin/python -m examples.phase1.runner stream
```

### 离线测试（无需 API Key）

```bash
.venv/bin/python -m pytest tests/examples/phase1 -q
```

### 真实模型 Smoke 测试（需要 MODEL_API_KEY）

```bash
MODEL_API_KEY=sk-... .venv/bin/python -m pytest tests/integration/phase1 -q
```

## 概念边界

- **Offline tests**: 使用 mock 和 fixture，不调用真实模型
- **Smoke tests**: 仅在 `MODEL_API_KEY` 存在时执行，用于验证真实模型接入
- **Runner**: 统一 CLI，退出码 0=成功, 1=异常, 2=未知示例, 3=缺少 Key

## 已知限制

- 无 MODEL_API_KEY 时 integration smoke 自动 skip
- 不执行全部七个示例的 smoke（仅 invoke/stream）以避免不可控费用
- 不在日志中打印 API Key 或 Prompt
- 离线测试不依赖外部网络
- `middleware-skills` 无 Key 可运行；skill 使用 Agent Skills YAML frontmatter
- Metadata 由 `SkillsMiddleware.before_agent()` 加载，`modify_request()` 注入仅在离线测试中验证

## 与 Phase 2 的边界

Phase 1 只建立教学示例和学习证据。Phase 2 将在此基础之上构建：
- 一主三从业务架构（Web/MySQL/RAGFlow Agent）
- FastAPI/WebSocket 接入
- React 工作台
- 报告生成
