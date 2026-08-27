# ADR 0005: Agent Research Product Convergence

**Status:** Accepted and documented design; implementation in progress

**Date:** 2026-08-14

The user-confirmed design baseline is documented across this ADR, the Phase 10
boundary, the detailed design specification, the Chinese product blueprint,
and the package implementation plan. Confirmation means the decisions are
fixed for implementation; it does not mean any Stage 1-3 exit gate has passed.

## Decision

The product converges on one user-facing mode: `agent-research`. The browser
and default API do not expose Profile, Runtime, tutorial, showcase, mock, or
fixture choices. Tutorial and showcase implementations remain only as explicit
internal regression adapters until the removal gate is satisfied.

The runtime uses an OpenAI-compatible model seam configured by
`MODEL_BASE_URL`, `MODEL_NAME`, and `MODEL_API_KEY`. Capability startup is
graded:

- required: the research model and the thread-scoped session workspace;
- optional: real-time Web retrieval, read-only MySQL, and the local knowledge
  index.

An unavailable optional capability never creates fabricated evidence. It is
reported as an explicit limitation and the task continues when synthesis is
still possible.

## Delivery Order

Implementation proceeds through three dependency-ordered stages:

1. **Stage 1: LLM + Web + upload** establishes the minimum research journey,
   WebSocket progress, thread-scoped files, and a validated report.
2. **Stage 2: MySQL + local knowledge** adds bounded read-only row retrieval,
   Qdrant Local + FastEmbed chunk retrieval, and source coverage states.
3. **Stage 3: complete citations and reports** makes claims fail closed,
   aligns API, WebSocket, React, JSON, Markdown, and PDF identities, completes
   failure/retry semantics, and removes legacy user-facing branches.

Design approval does not accept a stage. Each stage requires its own offline
exit gate; real Provider evidence requires separate explicit authorization.

## Invariants

- The existing HTTP, WebSocket, cancellation, thread-isolation, safe-path,
  read-only SQL, redaction, and artifact contracts remain compatibility
  constraints.
- The browser never receives Provider credentials or absolute server paths.
- The task registry owns exactly one terminal event per task.
- Every claim references validated evidence or is explicitly unsupported.
- Delivery is all-or-nothing for citation JSON, Markdown, and PDF.
- Automated verification uses injected fakes or local deterministic adapters;
  it does not call real LLMs, Tavily, MySQL, or external data sources.
- This decision authorizes neither deployment nor push, tag, release, or
  publication.

## Canonical Records

- [Phase 10 boundary](../phases/phase-10-agent-research-convergence.md)
- [Approved product design](../superpowers/specs/2026-08-13-agent-research-product-convergence-design.md)
- [Active implementation plan](../superpowers/plans/2026-08-14-agent-research-product-convergence.md)
- [Current phase status](../phase-status.md)

## Consequence

The product narrative, frontend information architecture, health contract, and
implementation plan now share one vocabulary and one staged acceptance model.
The design intentionally allows the existing adapters to remain during
migration, so compatibility tests can continue to protect accepted behavior
without making those adapters part of the product surface.
