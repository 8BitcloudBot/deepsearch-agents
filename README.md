# Agent Engineering Research Copilot

面向 AI Agent 框架选型、技术调研和工程决策的多智能体可信研究系统。

## Status

Phase 0 (`v0.0-foundation`) and Phase 1
(`v0.0-deepagents-examples`) are accepted. Phase 2 — Tutorial Parity
(`blocked_pending_node22_ci`): Tasks 0-6 are accepted at base HEAD `5988a8a` (including the Task 5 backend
closure); Task 7 (documentation, verification, CI) is **locally complete but
uncommitted** — its changes exist only in the worktree and are not part of
HEAD. The full local gate is green under the default Node v26.5.1 (Python
348 passed, frontend Vitest/lint/build/Playwright green, Compose MySQL
integration 6 passed), and a focused frontend compatibility rerun under
Homebrew Node v22.23.2 (`/opt/homebrew/opt/node@22/bin/node`) with pnpm
11.9.0 also passed (offline frozen install, Vitest 22 passed, lint, build,
Playwright 2 passed + 2 intentional cross-project skips), but release and
user acceptance are still **blocked** until the actual Ubuntu CI job — Node
22 with pnpm 10 — runs and passes its frontend gate (Playwright Chromium);
that job has not been run yet. Phase 3 has not started and
`v0.1-tutorial-parity` does not exist yet.
See [docs/phase-2-tutorial.md](./docs/phase-2-tutorial.md) §10-11 for the
gate requirements.

See [Current Phase Status](./docs/phase-status.md) for the live state and
[Roadmap](./docs/roadmap.md) for Phase 0-9 boundaries.

### Phase 2 Tutorial (chapters 8-14)

```bash
# Prerequisites: Python 3.12, Node.js 22, pnpm, uv. No API key needed in
# default mock mode (runtime + web + catalog + knowledge are all "mock").

# Backend
uv sync --extra dev --frozen
uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000

# Frontend (second terminal)
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend dev
```

Full runbook — provider matrix, mixed mock/real configuration, fresh-volume
and preserved-volume MySQL bootstrap with the SELECT-only `tutorial_reader`
account, external RAGFlow/Tavily/real-model opt-ins, API and WebSocket
contract examples, cancellation, limitations, CI gates and the chapter 8-14
matrix: [docs/phase-2-tutorial.md](./docs/phase-2-tutorial.md).

### Phase 1 Examples

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
uv sync --extra dev --frozen
pnpm --dir frontend install --frozen-lockfile

# Run tests
uv run pytest -q
pnpm --dir frontend exec vitest run

# Start MySQL (local dev)
# Uses host port 3307 -> container port 3306 by default, so another local
# MySQL project can continue using host port 3306.
docker compose up -d mysql

# Verify the environment after the container healthcheck is healthy
uv run python scripts/doctor.py --offline
uv run python scripts/doctor.py --mysql

# Start API
uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000

# Start frontend
pnpm --dir frontend dev
```

## Architecture

```
React Research Workspace → FastAPI Service → Research Runtime → Agents → Tools → Data Sources
```

当前架构边界参阅 [Roadmap](./docs/roadmap.md) 和
[Phase Documents](./docs/phases/)。历史设计稿保留在
[docs/superpowers/specs/](./docs/superpowers/specs/) 供审计参考。

## Documentation

- [Documentation Index](./docs/README.md)
- [Phase 2 Tutorial Runbook](./docs/phase-2-tutorial.md)
- [Roadmap](./docs/roadmap.md)
- [Phase Status](./docs/phase-status.md)
- [Phase Documents](./docs/phases/)
- [ADR Index](./docs/adr/)
- [Verification Evidence](./docs/verification/)
- [Changelog](./CHANGELOG.md)

## License

待确定。

## Acknowledgements

本项目参考 [didilili/deepsearch-agents](https://github.com/didilili/deepsearch-agents) 及配套教程进行学习。代码独立实现，保留独立提交历史。
