# Repeatable Portfolio Demonstration

本演示使用仓库内固定 fixture，通过现有 FastAPI、WebSocket、React、citation `2.0.0`
和 Markdown/PDF 交付契约运行。它不会读取模型或 Provider 凭据，不访问网络来源，也不
打开正式知识索引；正式知识构建与本地 smoke 见
[Formal Local Knowledge](knowledge-showcase.md)。

## Prerequisites

- Python `3.12`
- Node.js `22`
- 已按根 README 安装锁定的 Python 与 frontend 依赖

## Start The Success Scenario

终端一：

```bash
PYTHONPATH=. .venv/bin/python scripts/portfolio_demo.py \
  --scenario success --host 127.0.0.1 --port 8000
```

终端二：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000 pnpm --dir frontend dev \
  --host 127.0.0.1 --port 5173
```

打开 `http://127.0.0.1:5173/`，选择
`examples/portfolio_demo/showcase-notes.txt`，依次点击 **Upload** 和
**Start research**。推荐查询：

```text
Compare evidence-grounded Agent research approaches and explain the limits.
```

成功场景应显示：

- `Status: Success` 和唯一的 `task_completed`；
- Web、MySQL、Knowledge base、Uploaded file 四类来源；
- 2 个 claims、4 条 evidence、无 limitation；
- `live-citations.json`、`showcase-report.md`、`showcase-report.pdf`；
- 可下载的上传文件、Markdown 和 PDF。

## Run Honest Degradation

停止后端并使用同一端口重启：

```bash
PYTHONPATH=. .venv/bin/python scripts/portfolio_demo.py \
  --scenario degraded --host 127.0.0.1 --port 8000
```

新建 session，重新上传 fixture 并提交查询。结果保留 Web、MySQL 和 uploaded-file，
同时显示：

```text
knowledge-unavailable: formal knowledge collection is unavailable in this demo
```

该路径证明局部来源不可用不会被伪装为完整成功，也不会阻止其他来源交付。

## Run Formal Local Knowledge

正式索引建成后，可运行不调用真实 LLM 或外部 Provider 的正式知识场景：

```bash
PYTHONPATH=. .venv/bin/python scripts/portfolio_demo.py \
  --scenario formal-knowledge --host 127.0.0.1 --port 8000
```

前端启动方式不变。上传同一 fixture，并提交：

```text
What defenses help an agent treat retrieved RAG content as untrusted data rather than instructions?
```

该场景只把 knowledge 来源切换为真实 Qdrant Local + FastEmbed 检索；Web、MySQL 和上传
仍为仓库安全 fixture，回答为确定性本地文本。官方知识文档标题和完整 chunk locator
必须在 React、live citation JSON、Markdown 和 PDF 中保持同一身份。完整构建前提与证据
边界见 [Formal Local Knowledge](knowledge-showcase.md)。

## Run The Safe Failure Path

停止后端并重启：

```bash
PYTHONPATH=. .venv/bin/python scripts/portfolio_demo.py \
  --scenario failure --host 127.0.0.1 --port 8000
```

提交后，任务仍以唯一终态结束，citation document 不包含来源或 evidence，并显示安全的
`agent-failed` limitation。故意注入 executor 的本地路径和 token-shaped 文本不得出现在
WebSocket、JSON、Markdown、PDF 或 UI 中。

## Automated Verification

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/unit/phase9 tests/integration/phase9
```

这些测试覆盖场景白名单、loopback-only 服务地址、凭据隔离、四来源成功、结构化降级、
失败脱敏、三个产物、线程隔离和唯一终态。

## Interpretation Boundary

Phase 9 demo 是 deterministic offline contract reproduction。它不能替代 Phase 4.5 的
authorized real smoke，也不能证明真实模型质量、Provider 可用性、检索准确率、延迟、
成本、SLA 或生产就绪。

正式知识 evidence 是第三个独立分区：它使用真实本地文档、Qdrant Local 和 FastEmbed，
但不调用真实 LLM、Tavily 或 MySQL。它不能替代后续需要单独授权的真实 Showcase。
