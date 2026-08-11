# Phase 4.5 Research Showcase Implementation Plan

**Status:** P4.5-1 through P4.5-6 accepted in the current worktree. The Phase
4.5 portfolio checkpoint is ready for separately authorized Git closeout.

**Goal:** Deliver one portfolio-quality DeepAgents research workflow that uses
real source adapters when explicitly enabled, preserves deterministic offline
verification, links every displayed citation to a validated source locator,
and produces a coherent React plus Markdown/PDF experience.

**Execution rule:** The current Codex session implements one bounded package at
a time, reviews its own complete diff, runs proportionate gates, and accepts or
rejects the package before starting the next. Do not invoke Reasonix, use
DeepSeek as a coding worker, or dispatch subagents. Commit, tag, push, release,
global configuration changes, and real-provider execution require separate
explicit authorization.

## Frozen Baseline And Constraints

- Phase 4 implementation at `e817c79` and its later closeout documentation are
  read-only historical evidence.
- `APP_PROFILE=tutorial` and default offline tests retain current behavior.
- Real network/model/source access requires a dedicated showcase opt-in plus
  configured capability; missing configuration yields an explicit skip or
  structured limitation.
- Offline and live results use separate output roots, manifests and labels.
- Preserve thread isolation, read-only SQL, safe artifacts, redaction, event
  ordering, one terminal event and existing API compatibility.
- Use current DeepAgents/runtime/source adapter boundaries. Do not add another
  Agent framework or make the evaluation runner the product entry point.

## Package Sequence

```text
P4.5-1 Showcase profile + contracts
  -> P4.5-2 source locators
     -> P4.5-3 DeepAgents live integration
        -> P4.5-4 report/API/WS delivery
           -> P4.5-5 React polish
              -> P4.5-6 live smoke + integrated acceptance
```

## P4.5-1 — Showcase Profile And Live-Source Contracts

**Status:** Accepted on 2026-08-08. Codex verification: targeted unit tests
`90 passed`; full unit suite `758 passed`; Ruff check/format and
`git diff --check` passed. No real network, Provider, source or credential
access occurred; tutorial/default offline behavior remains compatible.

Define profile selection, capability checks, execution/evidence partitioning
and normalized live-source result contracts. Add tests proving the default
path never reads credentials or opens network connections, showcase mode is
explicit, and missing capabilities fail closed. Do not call a real source in
this package. Exit when downstream adapters can consume one frozen contract
without changing tutorial or offline behavior.

## P4.5-2 — Multi-Source Citation Locators

**Status:** Complete in the current worktree.

Implement and validate typed locators for Tavily Web, MySQL, local knowledge retrieval and
uploaded files through existing adapters. Cover canonicalization, stable IDs,
version/capture metadata, thread scope, safe display links, stale/missing
sources and secret/path redaction. Add adapter-level tests and one fixture per
source kind, but no real credentials or captured private content. Exit when
every enabled source can map evidence to a server-validated locator.

## P4.5-3 — DeepAgents Live Research Integration

**Status:** Complete in the current worktree.

Connect the main-agent/expert-worker research runtime to the normalized source
results and Phase 4 citation contracts. Keep worker failures isolated, preserve
one terminal event, deduplicate evidence and expose honest source limitations.
Use deterministic fakes for automated tests; add no orchestration strategies
beyond the accepted main-agent/worker path. Exit with a backend vertical slice
covering all four source kinds through the existing task runtime.

## P4.5-4 — Citation-Rich Delivery

**Status:** Complete in the current worktree.

Make the validated live citation records drive Markdown/PDF reports, artifact
downloads, thread-scoped APIs and non-terminal WebSocket progress. Reports must
show claim references, source metadata and limitations without credentials,
absolute paths or raw Provider responses. Exit with an end-to-end backend test
from task submission to events, citation retrieval and both report formats.

## P4.5-5 — React Showcase Polish

**Status:** Complete in the current worktree. See
[P4.5-5 evidence](../../verification/p4-5-5-evidence.md).

Refine the existing research workspace around the actual workflow: request,
agent/source progress, source coverage, claim-to-evidence inspection,
limitations and report delivery. Keep citations embedded in the research task;
do not create a separate evaluation dashboard. Add typed parsing, safe links,
loading/error/partial states, responsive tests and desktop/mobile browser
smoke. Exit when the showcase is readable and stable at both viewports.

## P4.5-6 — Real-Provider Showcase Smoke And Acceptance

**Status:** Accepted in the current worktree. The explicitly authorized real
smoke, integrated offline gates, desktop/mobile flow and corrected
uploaded-source browser download passed. See
[finalization evidence](../../verification/phase-4-5-finalization-evidence.md).

Create a fixed, documented opt-in smoke that uses configured LLM, Tavily and
available MySQL/knowledge/upload inputs without changing configuration or storing
secrets. Record capability matrix, timestamps, redacted provenance, source
coverage, artifact checks and known limitations in a live-only evidence file.
Then run the package-acceptance offline backend/frontend/static gates and
verify the smoke does not modify offline fixtures or aggregates. Codex alone
performs final acceptance; Git closeout remains a separate authorized action.

## Final Acceptance Evidence

- Full offline backend and frontend regression gates;
- focused source locator, API/event, report and UI tests;
- two deterministic offline executions with stable canonical outputs;
- desktop and mobile browser smoke for the complete research flow;
- explicit live smoke result or an honest capability-based skip report;
- secret, absolute-path, raw-response and cross-mode contamination scans;
- clean Git diff containing only accepted package changes, followed by an
  explicitly authorized Codex-owned checkpoint.

Acceptance of all six packages and frozen Phase 4.5 evidence is sufficient for
a portfolio checkpoint. Phase 5-8 remain optional and inactive until separately
authorized.
