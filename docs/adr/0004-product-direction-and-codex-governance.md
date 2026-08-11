# ADR 0004: Preserve the Multi-Source Research Product Direction

**Status:** Accepted

**Date:** 2026-08-09

## Context

The project was inspired by
[`didilili/deepsearch-agents`](https://github.com/didilili/deepsearch-agents).
Its durable technical and business identity is a DeepAgents research workflow
that gathers evidence from Web, structured data, knowledge bases, and uploaded
files, then delivers progress, citations, and reports through FastAPI,
WebSocket, React, Markdown, and PDF.

Phases 3 and 4 added reproducible evaluation, versioned fixtures,
fingerprints, and trustworthy citations. These are valuable engineering proof,
but they create a risk that the repository is presented as an Agent evaluation
platform instead of a multi-source research assistant.

## Decision

The product workflow remains the primary architecture and portfolio narrative:

```text
Research request
  -> DeepAgents main agent and expert workers
  -> Tavily Web / MySQL / local knowledge retrieval / uploaded files
  -> validated source locators, claims, and citations
  -> FastAPI + WebSocket progress and artifacts
  -> React workspace + Markdown/PDF reports
```

Evaluation runners, deterministic fixtures, comparison reports, fingerprints,
and citation metrics remain supporting proof. They may validate the workflow,
but they may not become a separate primary product surface or replace the live
research path.

Phase 4.5 is the active delivery stage. P4.5-2 through P4.5-6 must complete the
real multi-source citation and presentation closure. Acceptance of P4.5-6 is
enough to create a portfolio checkpoint.

Phases 5-8 are optional and require a new explicit product claim and user
authorization. If Phase 5 is activated, it must compare orchestration choices
inside the existing DeepAgents main-agent/worker workflow; it must not introduce
an unrelated Agent framework or standalone evaluation product.

Development is performed by Codex only. Historical Reasonix/DeepSeek execution
records remain audit history and are not current instructions.

## Consequences

- Product-facing work prioritizes source retrieval, trustworthy citations,
  progress, reports, and the React research workspace.
- Offline and live evidence stay partitioned; fixture metrics never represent
  real-provider or real-source quality.
- Persistence, recovery, approval, budget governance, and broader observability
  do not block the portfolio checkpoint unless the project explicitly claims
  those production capabilities.
- Verification is proportional to change risk locally, while complete offline
  gates remain package-acceptance and CI responsibilities.

## Revisit Conditions

Revisit this decision only if the user explicitly changes the product from a
multi-source research assistant to an evaluation platform or production Agent
control plane.
