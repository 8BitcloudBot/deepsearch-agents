# Agent Engineering Research Copilot

面向 AI Agent 框架选型、技术调研和工程决策的多智能体可信研究系统。

## Status

Phase 0 (`v0.0-foundation`) through Phase 4.5 — Research Showcase and
Live-Source Parity are accepted. The multi-source showcase is published as
[`v0.2-portfolio-showcase`](https://github.com/8BitcloudBot/deepsearch-agents/releases/tag/v0.2-portfolio-showcase).
Phase 9 — Portfolio Release is active for README, architecture, demonstration,
failure-review, screenshot, and interview evidence. Phase 5-8 remain optional
and require separate authorization.

See [Current Phase Status](./docs/phase-status.md) for the live state,
[Roadmap](./docs/roadmap.md) for Phase 0-9 boundaries, and the
[Phase 2 Tutorial Parity Runbook](./docs/runbooks/phase-2-tutorial-parity.md)
for the local mock reproduction and release verification commands.

The accepted research profile preserves the original DeepAgents workflow:
orchestrated Tavily Web, read-only MySQL, local knowledge retrieval,
uploaded-file and Markdown/PDF research delivery. Citation and evaluation
evidence strengthens that workflow; it does not turn offline fixtures into
claims about real Provider or live-source quality.
The active-stage boundary is documented in
[Phase 9](./docs/phases/phase-9-portfolio-release.md). The accepted showcase
boundary remains recorded in
[Phase 4.5](./docs/phases/phase-4-5-research-showcase.md).

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

The commands above use the offline tutorial/mock profile unless Showcase is
explicitly enabled. They do not require model or Provider credentials.

### Showcase opt-in

Start from the commented Phase 4.5 block in `.env.example` and enable only the
capabilities you intend to exercise. Showcase itself requires a configured
model. Each source remains independently gated:

| Source | Provider/configuration | Behavior when unavailable |
|---|---|---|
| Web | Tavily and `TAVILY_API_KEY` | structured Web limitation |
| MySQL | read-only MySQL settings | structured MySQL limitation |
| Knowledge base | Qdrant Local index; no provider key | structured knowledge limitation |
| Uploaded file | thread-scoped upload workspace | omitted when not enabled |

Real Provider and model smoke is separate from normal startup and tests. It
requires `PHASE45_REAL_SHOWCASE_SMOKE=1`, usable enabled capabilities, and
explicit user authorization; do not treat the flag alone as authorization.

### Local knowledge manifest

Knowledge indexing consumes one explicitly selected UTF-8 JSON manifest; it
does not crawl directories, parse documents, or build the formal knowledge
corpus. Validate a manifest without loading FastEmbed or creating an index:

```bash
PYTHONPATH=. .venv/bin/python scripts/index_knowledge.py \
  --manifest /explicit/path/to/manifest.json \
  --index-path .data/knowledge-index \
  --collection deepsearch-showcase-v1 \
  --validate-only
```

Remove `--validate-only` only for an intentional local indexing run. That mode
uses the supported FastEmbed model and may populate `.cache/fastembed` when the
model is not already cached. If `.data/knowledge-index` is absent or invalid,
Showcase continues with its other enabled sources and reports knowledge as
unavailable instead of fabricating evidence.

The formal knowledge corpus, ingestion/chunking pipeline, retrieval-quality
dataset, and accuracy evaluation have not been built. Current fixtures and the
local adapter smoke prove contracts and citation flow only.

## Architecture

```
React Research Workspace → FastAPI Service → Research Runtime → Agents → Tools → Data Sources
```

当前架构边界参阅 [Roadmap](./docs/roadmap.md) 和
[Phase Documents](./docs/phases/)。历史设计稿保留在
[docs/superpowers/specs/](./docs/superpowers/specs/) 供审计参考。

## Documentation

- [Documentation Index](./docs/README.md)
- [Roadmap](./docs/roadmap.md)
- [Phase Status](./docs/phase-status.md)
- [Phase Documents](./docs/phases/)
- [ADR Index](./docs/adr/)
- [Phase 2 Runbook (mock reproduction + gates)](./docs/runbooks/phase-2-tutorial-parity.md)
- [Verification Evidence](./docs/verification/)
- [Changelog](./CHANGELOG.md)

## License

待确定。

## Acknowledgements

本项目参考 [didilili/deepsearch-agents](https://github.com/didilili/deepsearch-agents) 及配套教程进行学习。代码独立实现，保留独立提交历史。
