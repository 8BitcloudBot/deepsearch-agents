# Agent Engineering Research Copilot

面向 AI Agent 框架选型、技术调研和工程决策的多智能体可信研究系统。

## Status

⚠️ **Phase 1 — DeepAgents Capability Examples** (in progress)

Phase 0 foundation accepted (`v0.0-foundation`). Phase 1 establishes DeepAgents/LangGraph learning examples. Agent business capabilities and full system integration are not yet implemented.

### Phase 1 Quick Start

```bash
# Run Phase 1 examples
.venv/bin/python -m examples.phase1.runner --list

# Offline tests (no API key needed)
.venv/bin/python -m pytest tests/examples/phase1 -q

# With API key
MODEL_API_KEY=sk-... .venv/bin/python -m examples.phase1.runner invoke
```

See [examples/phase1/README.md](./examples/phase1/README.md) for details.

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
# Uses host port 3307 -> container port 3306 by default, so another local
# MySQL project can continue using host port 3306.
docker compose up -d mysql

# Verify the environment after the container healthcheck is healthy
uv run python scripts/doctor.py --offline
uv run python scripts/doctor.py --mysql

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
