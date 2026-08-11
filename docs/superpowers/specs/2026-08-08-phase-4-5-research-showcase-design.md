# Phase 4.5 Research Showcase Design

**Status:** Approved; P4.5-1 accepted, P4.5-2 ready

The durable product-direction decision is recorded in
[`ADR 0004`](../../adr/0004-product-direction-and-codex-governance.md).

## Context

Phase 3 and Phase 4 made the system reproducible and citation-aware, but their
offline fixtures and deterministic runners now occupy more of the repository
narrative than the original deep-research product flow. The project must keep
those engineering proofs while restoring the visible center of gravity:
DeepAgents coordinating Web, database, knowledge-base and uploaded-file
research through a streaming workspace and delivered report.

## Decision

Insert Phase 4.5 before orchestration experiments. Phase 4.5 is a vertical
product-integration stage, not another evaluation stage. It adds an explicit
showcase profile that binds existing source adapters to one normalized locator
contract, feeds those sources through the existing DeepAgents-style runtime,
and delivers citations in the same API, WebSocket, React and Markdown/PDF flow.

## Execution Modes

| Mode | Network / credentials | Evidence use |
|---|---|---|
| Offline/default | Never implicit | deterministic regression and evaluation |
| Tutorial/mock | local tutorial contracts | demo compatibility |
| Showcase/live | explicit opt-in plus configured capabilities | separate real-run smoke evidence only |

The modes share validated domain contracts but never share result aggregates.
A real-run result cannot update an offline benchmark report, and an offline
metric cannot be presented as live-source performance.

## Source Locator Contract

All adapters produce a normalized source descriptor with stable source ID,
kind, title, captured/version metadata, bounded display text and a typed
locator. Locator payloads remain adapter-specific:

- Tavily/Web: canonical URL, retrieval timestamp and bounded content span;
- MySQL: approved connection alias, schema/table identity, query fingerprint
  and row/column identity, never credentials or raw connection strings;
- Local knowledge retrieval: collection, document, chunk and version identity;
- uploaded file: thread-scoped artifact identity plus page/line/span.

The server validates all locators before emitting API/event data. The frontend
does not construct arbitrary remote links or filesystem paths.

## Runtime And Delivery

The main agent plans research and delegates bounded source work to existing
expert workers. Worker results are normalized, deduplicated and converted to
evidence before report claims are finalized. Partial source failures become
limitations; they do not fabricate evidence or create a second terminal event.
The final report and citation panel use the same validated citation records.

## User Experience

The React workspace remains the product surface. It shows research progress,
source coverage, claim-to-evidence navigation, limitations and downloadable
Markdown/PDF artifacts within the task flow. Evaluation metadata may support
the display but must not become a separate primary dashboard.

## Consequences

- Phase 5 can measure orchestration strategies against a real product-shaped
  workflow instead of an isolated runner.
- Live integrations introduce availability and credential variance, so their
  smoke evidence is necessarily explicit, bounded and separate.
- Phase 4 contracts remain useful and frozen; adapter integration extends
  their inputs without rewriting historical fixtures or acceptance evidence.

## Deferred

S2-S4 experiments, distributed tracing, recovery, approval and cost governance
remain Phase 5-8 concerns. A portfolio release may follow Phase 6; Phase 7/8
are necessary only for corresponding production-level claims.
