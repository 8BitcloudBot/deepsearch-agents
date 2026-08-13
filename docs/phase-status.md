# Current Phase Status

**Updated:** 2026-08-13

**Branch:** `main`

**Portfolio release:** `v1.0-portfolio` (Phase 9 boundary)

**Current phase:** Phase 9 — Portfolio Release, accepted

**Current package:** P9-1 through P9-5 and formal local knowledge K1-K6 are
accepted. The actual-index `formal-knowledge` demo and the one
authorized real Showcase smoke both close through the existing
upload/task/citation/report path. Formal-knowledge browser screenshots were
explicitly waived; no viewport claim is made for that fixture. The
`v1.0-portfolio` boundary includes the repository, tag, and GitHub Release; it
does not include deployment.

The knowledge retrieval route is vendor-neutral: Showcase uses the
`KnowledgeRetriever` contract with Qdrant Local + FastEmbed by default. A
formal local pack now freezes 6 official documents into 140 semantic chunks
and a 13-question acceptance set. The third-party bodies, built manifest,
`.data/knowledge-index`, evaluation result, and `.cache/fastembed` remain local
and ignored by Git; only source metadata, licenses, hashes, catalog, question
set, scripts, tests, and evidence are public.

## Product Direction

Deepsearch remains a multi-source DeepAgents research product. The primary
delivery flow is:

```text
Research request
  -> DeepAgents main agent and expert workers
  -> Tavily Web / MySQL / local knowledge retrieval / uploaded files
  -> validated source locators, claims, and citations
  -> FastAPI + WebSocket progress and artifacts
  -> React workspace + Markdown/PDF reports
```

Evaluation datasets, deterministic runners, fingerprints, and citation metrics
are supporting evidence. They must not replace the research workflow as the
product entry point. See [ADR 0004](adr/0004-product-direction-and-codex-governance.md).

## Accepted Baseline

| Stage | Status | Canonical evidence |
|---|---|---|
| Phase 0 — Foundation | accepted | `v0.0-foundation` |
| Phase 1 — Capability Examples | accepted | `v0.0-deepagents-examples` |
| Phase 2 — Tutorial Parity | accepted | `v0.1.1-tutorial-parity` |
| Phase 3 — Research Evaluation | accepted | [Phase 3 evidence](verification/phase-3-evidence.md) |
| Phase 4 — Trustworthy Citations | accepted | [Phase 4 evidence](verification/phase-4-evidence.md) |
| Phase 4.5 — Research Showcase | released | `v0.2-portfolio-showcase` at `bab5da4` |

Historical command output and test counts stay in the linked evidence records;
they are not repeated here.

## Phase 4.5 Release Baseline

| Package | Status | Exit condition |
|---|---|---|
| P4.5-1 — Showcase Profile And Live-Source Contracts | accepted | explicit profile, capability and evidence partition contracts |
| P4.5-2 — Multi-Source Citation Locators | accepted at checkpoint `3a84c58` | all enabled sources map to validated, safe locators |
| P4.5-3 — DeepAgents Live Research Integration | accepted at checkpoint `3a84c58` | four source kinds close through the existing task runtime |
| P4.5-4 — Citation-Rich Delivery | accepted at checkpoint `3a84c58` | API, WebSocket, Markdown and PDF share validated citations |
| P4.5-5 — React Showcase Polish | accepted at checkpoint `3a84c58` | complete desktop/mobile research journey is readable |
| Knowledge retrieval migration | accepted at checkpoint `3a84c58` | Qdrant Local + FastEmbed adapters, fingerprints and offline citation chain |
| P4.5-6 — Live Smoke And Integrated Acceptance | accepted at checkpoint `3a84c58` | real smoke, offline gates and desktop/mobile browser acceptance passed |

P4.5-6 acceptance is sufficient for a portfolio checkpoint. Phase 5-8 are
optional follow-on work and require a new explicit authorization.

The P4.5-6 acceptance record is
[Phase 4.5 finalization evidence](verification/phase-4-5-finalization-evidence.md).
The accepted implementation checkpoint is `3a84c58`; the published release tag
`v0.2-portfolio-showcase` points to `bab5da4`, which includes the repository
import-path CI fix. The GitHub Release is published. Deployment has not been
performed.

The earlier Phase 4.5 real smoke correctly recorded formal knowledge as
unavailable at that time. The later local package now proves formal Qdrant +
FastEmbed retrieval, stable locators, citation schema `2.0.0`, Markdown, PDF,
and React component rendering without rerunning a real model or Provider. Its
`13 passed` result is a frozen acceptance set, not measured retrieval accuracy.

## Phase 9 Local Package

- The public README now centers the verified multi-source research workflow,
  offline demonstration and explicit limits.
- A credential-free deterministic demo reproduces success, knowledge-degraded
  and safe-failure paths through the existing API, WebSocket, citation and
  report contracts.
- Architecture, repeatable demonstration, repository-safe desktop/mobile
  screenshots, failure retrospective, interview STAR narratives and a claim
  evidence map are present under `docs/portfolio/` and `docs/assets/portfolio/`.
- Phase 9 still uses existing Phase 3/4/4.5 evidence for the main product. The
  formal knowledge extension adds 6 frozen official documents and a 13-question
  local acceptance set; it did not create `portfolio-100`, `hidden-20`, or new
  real-provider metrics.
- Phase 5-8 remain optional and require separate authorization.

## Formal Knowledge Package

- K1-K4 are accepted locally: official source inventory, explicit semantic
  build, validate-only behavior, idempotent path-backed index, and fixed
  retrieval expectations are recorded in
  [formal knowledge evidence](verification/showcase-knowledge-evidence.md).
- The backend K5 smoke passes through local Qdrant + FastEmbed, the knowledge
  source tool, validated live citations, Markdown, and PDF; React component
  tests preserve the official title and full chunk locator.
- The Phase 9 `formal-knowledge` scenario opens the actual local index and
  carries its evidence through upload, task, live-citation, Markdown, and PDF
  contracts without a real model or Provider.
- The sandbox rejected both loopback server binds, and the environment safety
  reviewer denied their controlled escalation. The user explicitly waived
  formal-knowledge browser screenshots, so no `1440x900` or `375x812` E2E claim
  is made for that fixture.
- One real model Showcase smoke was explicitly authorized and passed with only
  `knowledge,uploaded-file` enabled. It produced 28 sources and 28 evidence
  items across the uploaded span and local knowledge chunks; the redacted
  artifact also records repeated unsuccessful tool attempts as limitations.

The Phase 9 package acceptance record is
[Phase 9 portfolio evidence](verification/phase-9-portfolio-evidence.md).

## Development Boundary

- Development is performed by the current Codex session only.
- Do not invoke Reasonix, use DeepSeek as a coding worker, or dispatch subagents.
- Default and automated paths remain deterministic and offline.
- Real providers and live sources require explicit opt-in, configured
  capabilities, and separate user authorization.
- Preserve thread isolation, read-only SQL, safe paths, redaction, event
  ordering, one terminal event, API compatibility, and artifact safety.
- Local verification is proportional to change risk; complete offline gates run
  at package acceptance, CI, or release boundaries.
- Future provider, push, tag, release, and deployment actions require separate
  authorization; the one-time `v1.0-portfolio` publication authorization does
  not extend beyond this release.

## Canonical Documents

- [Repository instructions](../AGENTS.md)
- [Documentation index](README.md)
- [Roadmap](roadmap.md)
- [Product direction decision](adr/0004-product-direction-and-codex-governance.md)
- [Phase 9 stage](phases/phase-9-portfolio-release.md)
- [Accepted Phase 4.5 stage](phases/phase-4-5-research-showcase.md)

Historical plans, handoffs, and evidence are not current execution instructions
unless one of the documents above links a specific record for a concrete task.
