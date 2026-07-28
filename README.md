# Agent Engineering Research Copilot

面向 AI Agent 框架选型、技术调研和工程决策的多智能体可信研究系统。

## Status

⚠️ **Early Development — Phase 0 (Foundation)**

本项目当前处于 Phase 0 基础设施阶段。Agent 业务能力、教程实现、外部服务集成和报告生成等功能尚未实现。

## Quick Start

```bash
# Prerequisites: Python 3.12, Node.js 22, Docker, pnpm, uv

# Install dependencies
uv sync --dev
pnpm install --frozen-lockfile --dir frontend

# Run tests
uv run pytest -q
pnpm --dir frontend test -- --run

# Start MySQL (local dev)
docker compose up -d mysql

# Start API
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# Start frontend
pnpm --dir frontend dev
```

## Architecture

```
React Research Workspace → FastAPI Service → Research Runtime → Agents → Tools → Data Sources
```

详细的架构设计请参阅 [docs/superpowers/specs/](./docs/superpowers/specs/)。

## Documentation

- [Phase Status](./docs/phase-status.md)
- [ADR Index](./docs/adr/)
- [Verification Evidence](./docs/verification/)
- [Changelog](./CHANGELOG.md)

## License

待确定。

## Acknowledgements

本项目参考 [didilili/deepsearch-agents](https://github.com/didilili/deepsearch-agents) 及配套教程进行学习。代码独立实现，保留独立提交历史。
