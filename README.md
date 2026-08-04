# Agent Engineering Research Copilot

面向 AI Agent 框架选型、技术调研和工程决策的多智能体研究工作台。

## Status

Phase 0 and Phase 1 are accepted. Phase 2 — Tutorial Parity: Tasks 0-7 are
accepted, and the B3 (failure/cancel/rerun) closure tests plus the initial
B4 evidence documentation are committed and CI-verified at the remote
branch head `27832bc` (`codex/phase2a-websocket-e2e`): commit
`27832bc5c3ba31d23a77e3187bf9e0e016a504c4` (parent `9839440`) was pushed
and GitHub Actions push run **30906797763** (head 27832bc) is **success** —
Python 3.12 install/tests/lint/format/pre-commit/compose/doctor and the
frontend Node 22 + pnpm 10 frozen install, Chromium install, Vitest, lint,
build, and Playwright browser tests are all green. The earlier Task 7 CI
gate (run 30878728964, head 9839440) remains as historical evidence.

`v0.1-tutorial-parity` has **not** been created and nothing has been
released; Phase 3-9 remain deferred. Default startup is full mock mode
with no API key; real Tavily/RAGFlow/model providers are opt-in and
require credentials. The current worktree document edits are an
evidence-only status refresh — they do not change runtime or test
behavior and are not yet committed, so no commit SHA or CI run is claimed
for them.

The current execution order is B1-B4 in the
[pragmatic-closure entry](./docs/pragmatic-closure.md): remote CI, reproducible
mock happy path, failure/cancel/rerun paths, then evidence closure. See
[Current Phase Status](./docs/phase-status.md) for facts and
[Roadmap](./docs/roadmap.md) for future boundaries. Historical plans, specs,
and handoffs are not current instructions.

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
uv run python -m pytest tests/ -q
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

- [Pragmatic Closure Entry](./docs/pragmatic-closure.md)
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
