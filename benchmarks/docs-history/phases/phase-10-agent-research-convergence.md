# Phase 10 — Agent Research Product Convergence

**Status:** Implemented; real acceptance complete

**Entry gate:** Phase 9 (`v1.0-portfolio`) remains accepted. This phase changes
the active product after that release boundary and does not rewrite Phase 9
evidence.

## Goal

Deliver one real `agent-research` product in which:

- the user chooses the allowed research sources;
- a real OpenAI-compatible LLM plans, researches, reviews evidence gaps, and
  synthesizes;
- the application guarantees selected-source execution and records truthful
  per-source outcomes;
- validated claims and citations flow through FastAPI, WebSocket, React, JSON,
  and Markdown;
- tutorial, showcase, mock, fixture, and offline-demo product paths are absent.

The target flow is:

```text
question + user source selection + uploaded files
  -> real LLM plan
  -> application-owned coordinator and real expert workers
  -> Web / read-only MySQL / local knowledge / uploaded-file outcomes
  -> normalized evidence and coverage review
  -> real LLM synthesis
  -> validated schema 4.0.0 result and reports
```

## Canonical Design

The current implementation contract is the
[User-Directed Real-Provider Research Design](../superpowers/specs/2026-08-14-user-directed-real-provider-research-design.md).
It supersedes the 2026-08-13 convergence design and the implementation plan
derived from that older design.

The earlier implementation remains useful only as code to migrate or delete.
Its schema `3.0.0`, free-form top-level DeepAgents `task` loop,
capability-inferred source coverage, and fake/local complete research journeys
are not accepted as the target architecture.

## Confirmed Product Decisions

1. The browser exposes only `agent-research`.
2. Web is selected by default when ready.
3. MySQL and local knowledge are selected explicitly by the user.
4. Uploaded files are automatically included after upload and may be removed
   before the run starts.
5. No upload is displayed as `无参考`.
6. LLM-only research is allowed and explicitly carries no externally validated
   citations.
7. Unselected sources do not create limitations.
8. Selected sources must report matched, no-match, unavailable, or failed; the
   model may not silently skip them.
9. Search depth follows unresolved evidence questions rather than a fixed
   search count.
10. Outer safety budgets stop loss of control but do not define the research
    strategy.
11. Invalid model citation references are filtered at claim level without
    destroying valid evidence or reports.
12. Real Providers drive product integration and browser acceptance.
13. Credential-free tests remain only for pure domain, security, and adapter
    contracts.

## Source Semantics

Health and run outcomes are independent. Health answers whether a capability
can be attempted. The canonical result answers what happened in this run.

Each source has one explicit run status:

```text
not-selected
no-reference
planned
running
matched
no-match
unavailable
failed
```

The result also records attempt, query, hit, evidence, and cited-evidence
counts. This supports user-facing statements such as:

```text
会话文件：无参考
结构化数据：未选择
本地知识库：已检索，无相关数据命中
实时网络：命中 8 条，其中 3 条用于结论
```

No-reference, not-selected, and successful no-match outcomes do not by
themselves degrade a run.

## Delivery Packages

### P10-R1 — Request, Plan, And Source-Run Domain

Introduce the user source-selection request, LLM-produced research plan,
application-owned source execution ledger, and canonical schema `4.0.0`.

**Exit gate:** request validation, source-run transitions, evidence identities,
and document round trips prove every selected and unselected source state.

### P10-R2 — Explicit Real-LLM Coordinator

Replace free top-level worker delegation with an explicit graph owned by the
application. The real main LLM plans and synthesizes; selected expert workers
execute through the coordinator.

**Exit gate:** one run cannot silently skip a selected source or fan out
duplicate workers, and usable evidence survives outer-budget exhaustion.

### P10-R3 — Real Source Execution

Integrate adaptive Tavily Web research, user-selected read-only MySQL,
user-selected local knowledge, and automatically selected uploaded files.

**Exit gate:** every selected source reports matched, no-match, unavailable, or
failed with validated locators and evidence IDs.

### P10-R4 — Citation And Delivery Contract

Filter unknown model evidence IDs at claim level, carry plan and source-run
truth through the result, and produce the exact JSON/Markdown set.

**Exit gate:** invalid claims do not invalidate unrelated evidence; all delivery
surfaces share schema `4.0.0` identities.

### P10-R5 — User-Directed React Workspace

Add source toggles, automatic uploaded-file inclusion, a pre-run research-mode
summary, source-semantic progress, and truthful result coverage.

**Exit gate:** desktop and mobile views distinguish no-reference, not-selected,
matched, no-match, unavailable, and failed without inferring run state from
health.

### P10-R6 — Legacy Product Removal

Delete tutorial, showcase, mock, fixture, deterministic demo, Profile, and
complete fake/local browser journey assembly. Retain only pure domain,
security, and Provider adapter tests that protect the real product.

**Exit gate:** production and test application factories cannot start a mock or
offline research product, and no user-facing documentation describes one.

### P10-R7 — Real-Provider Acceptance

Run the configured real acceptance matrix:

1. LLM + Web without uploads;
2. LLM + Web with uploads;
3. selected MySQL;
4. selected local knowledge;
5. selected mixed sources;
6. intentional LLM-only research;
7. real no-match and classified failure paths;
8. desktop/mobile JSON and Markdown delivery.

**Exit gate:** selected-source execution, terminal status, citations, artifacts,
and rendered UI match the approved design. Results do not imply unmeasured
quality, cost, latency, SLA, or production readiness.

## Verification Boundary

Credential-free automation proves only deterministic contracts:

- source-selection and state transitions;
- query, URL, and content deduplication;
- path, upload, SQL, redaction, and locator safety;
- claim-level citation filtering;
- exactly one terminal event;
- atomic artifact delivery;
- frontend parsing and rendering;
- Provider adapter request, response, and failure classification.

Real model and source behavior is accepted only through the real-Provider
matrix. A fake adapter test is not a product journey, model-quality result, or
release claim.

## Current Boundary

P10-R1, R2, R4, R5, and R6 are implemented and accepted locally. P10-R3 is
implemented across Web, MySQL, local knowledge, and uploads; real Web, upload,
knowledge no-match, and selected MySQL rows are accepted. P10-R7 also accepts
LLM-only, cancellation, desktop/mobile composition, schema `4.0.0`, and
JSON/Markdown delivery. The selected MySQL row used a one-time explicit
`MYSQL_ALLOWED_TABLES` configuration (仅按允许列表执行) and preserved its executed query count and
evidence after the model-call safety limit.

The redacted results are in the
[report-quality closure acceptance record](../superpowers/acceptance/2026-08-15-research-report-quality-closure.md).
The [replacement implementation plan](../superpowers/plans/2026-08-14-user-directed-real-provider-research.md)
remains the implementation specification, not a source of current status.

No push, tag, release, publication, or deployment is included. Production
credentials or data remain out of scope unless separately authorized.
