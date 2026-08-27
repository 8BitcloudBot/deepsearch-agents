# Phase 9 Portfolio Evidence

**Date:** 2026-08-12

**Baseline:** local `main` at `2d07e3d`, one commit ahead of `origin/main`.

**Scope:** P9-1 through P9-5 — public README, evidence map, deterministic demo,
architecture, screenshots, failure retrospective, interview STAR narratives
and canonical status synchronization.

The unrelated untracked `扩展计划.md` was not read, modified, staged or
committed. No real Provider, live source, production data, push, tag, Release
or deployment was used.

## Deliverables

- Root README structured around the multi-source DeepAgents research flow,
  verified contracts, repeatable offline demo and explicit limitations.
- `docs/portfolio/` reader guide, architecture, demo runbook, evidence map,
  failure retrospective and interview evidence.
- A fixture-backed `examples.portfolio_demo` runtime plus loopback-only CLI.
- Success, degraded and failure scenarios reuse the existing FastAPI,
  WebSocket, citation schema `2.0.0`, React and Markdown/PDF delivery contracts.
- Repository-safe `1440x900` desktop success/degraded screenshots and a
  `375x812` mobile success screenshot.

## Browser Acceptance

The local React workspace and deterministic ASGI demo were exercised without
credentials or external network sources.

| Scenario | Viewport | Result |
|---|---:|---|
| success | `1440x900` | Success, 2 claims, 4 evidence records, four source kinds, no limitation, three artifacts |
| success | `375x812` | Research results and evidence cards readable in one column; no horizontal overflow |
| degraded | `1440x900` | 3 evidence records; Web/MySQL/upload retained; knowledge reports `0 sources · limited` and `knowledge-unavailable` |

For all three captures, `scrollWidth == clientWidth`. Visible text contained no
`/Users/` absolute path, injected `raw-secret` value or accidental `<secret>`
placeholder. Images are real PNG files with dimensions matching their names and
documentation.

Browser acceptance found two demo integration defects before capture:

1. The Web fixture was incorrectly assigned a thread ID, so the frontend
   parser correctly rejected the citation document. A backend regression now
   requires non-upload evidence to have `thread_id=null`.
2. The default knowledge title combined long identifier tokens and triggered
   the existing opaque-secret redaction rule. The demo now passes an explicit
   repository-safe fixture title; the production redactor was not weakened.

## Focused Gates

The following fresh commands passed during implementation:

```text
PYTHONPATH=. .venv/bin/pytest -q tests/unit/phase9 tests/integration/phase9
15 passed

PYTHONPATH=. .venv/bin/pytest -q tests/unit/phase4_5 \
  tests/integration/phase4_5/test_showcase_delivery_api.py \
  tests/integration/phase4_5/test_showcase_runtime.py
147 passed

pnpm --dir frontend exec vitest run src/workbench/ShowcaseResults.test.tsx
37 passed
```

## Package Acceptance Gates

All commands below were run fresh on the final Phase 9 worktree and exited `0`.

| Command | Result |
|---|---:|
| `PYTHONPATH=. .venv/bin/pytest -q` | `1148 passed, 15 skipped`; one existing Starlette/httpx deprecation warning |
| `pnpm --dir frontend exec vitest run` | `120 passed` |
| `pnpm --dir frontend lint` | passed |
| `pnpm --dir frontend build` | 31 modules transformed; production build passed |
| `.venv/bin/ruff check .` | passed |
| `.venv/bin/ruff format --check app tests scripts examples` | 173 files already formatted |
| `.venv/bin/pre-commit run --files README.md docs/README.md docs/phase-status.md docs/roadmap.md docs/phases/README.md docs/phases/phase-9-portfolio-release.md docs/portfolio/README.md docs/portfolio/architecture.md docs/portfolio/demo.md docs/portfolio/evidence-map.md docs/portfolio/failure-retrospective.md docs/portfolio/interview-evidence.md docs/verification/phase-9-portfolio-evidence.md docs/assets/portfolio/showcase-desktop.png docs/assets/portfolio/showcase-mobile.png docs/assets/portfolio/showcase-degraded.png examples/portfolio_demo/__init__.py examples/portfolio_demo/app.py examples/portfolio_demo/runtime.py examples/portfolio_demo/fixtures/web.json examples/portfolio_demo/fixtures/mysql.json examples/portfolio_demo/fixtures/knowledge.json examples/portfolio_demo/showcase-notes.txt scripts/portfolio_demo.py tests/unit/phase9/__init__.py tests/unit/phase9/test_portfolio_demo.py tests/integration/phase9/__init__.py tests/integration/phase9/test_portfolio_demo_app.py` | Ruff, Ruff format and Detect Secrets passed |
| `git diff --check` | passed |
| local Markdown target check | `markdown-links=pass` |

The success scenario was also executed twice in separate temporary workspaces
through the real upload/task/live-citation API boundary. The complete canonical
citation JSON matched byte-for-byte:

```text
phase9-demo-repro=pass
sha256=0d4a7ecaaaa900e37c46cf73e7ec3c46dde1074cbf75aff88ea2421ed2d3097a
bytes=4830
```

The pre-commit command explicitly listed the Phase 9 files and excluded the
unrelated untracked `扩展计划.md`.

## K6 Addendum

After the original P9-1 through P9-5 evidence was recorded, the user explicitly
authorized one real Showcase smoke. It loaded `.env` without printing values and
enabled only `knowledge,uploaded-file` with `KNOWLEDGE_PROVIDER=qdrant-local`;
Tavily and MySQL were not constructed. The command completed with `2 passed` in
`120.44s` and the known FastEmbed pooling warning.

The temporary citation document contained a non-empty answer, 28 sources and 28
evidence items: one uploaded-file span and 27 local knowledge chunks. The
canonical knowledge locator remained
`deepsearch-showcase-v1:document:chunk`; citation JSON, Markdown, and PDF all
passed the existing artifact and leak checks. The model made repeated tool
attempts, so the redacted document also retained `knowledge-unavailable`,
`source-failed`, and `no-evidence` limitations. These observations are not
quality, cost, latency, or success-rate metrics.

The user waived formal-knowledge browser screenshots. K5 is accepted at the
actual-index backend, citation/report, React contract, and functional-chain
boundaries; no viewport E2E claim is made for that fixture.

## Acceptance Decision

P9-1 through P9-5 and the formal knowledge K1-K6 package are **accepted**.
The public narrative, evidence boundaries, deterministic demonstration, screenshots,
retrospective, interview materials, and the authorized K6 result are mutually
consistent and verified. The `v1.0-portfolio` push, tag, and GitHub Release were
not part of the verification commands recorded above; they are separate release
actions. Deployment was not performed and is outside this release boundary.
