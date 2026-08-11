# Current Phase Status

**Updated:** 2026-08-12

**Branch:** `main`

**Current baseline:** `ce3e2f9` — P4.5-1 accepted; P4.5-2 through P4.5-5 are
implemented in the current worktree

**Current phase:** Phase 4.5 — Research Showcase and Live-Source Parity

**Next package:** none; Phase 4.5 portfolio checkpoint ready for authorized Git closeout

The knowledge retrieval route is now vendor-neutral: Showcase uses the
`KnowledgeRetriever` contract with Qdrant Local + FastEmbed by default. No
formal knowledge corpus has been built. The configured `.data/knowledge-index`
remains absent; `.cache/fastembed` was populated only by the separately
authorized adapter smoke. Both paths are ignored by Git.

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
| P4.5-1 — Showcase Profile And Contracts | accepted | baseline `ce3e2f9` |

Historical command output and test counts stay in the linked evidence records;
they are not repeated here.

## Active Package Sequence

| Package | Status | Exit condition |
|---|---|---|
| P4.5-1 — Showcase Profile And Live-Source Contracts | accepted | explicit profile, capability and evidence partition contracts |
| P4.5-2 — Multi-Source Citation Locators | complete in current worktree | all enabled sources map to validated, safe locators |
| P4.5-3 — DeepAgents Live Research Integration | complete in current worktree | four source kinds close through the existing task runtime |
| P4.5-4 — Citation-Rich Delivery | complete in current worktree | API, WebSocket, Markdown and PDF share validated citations |
| P4.5-5 — React Showcase Polish | complete in current worktree | complete desktop/mobile research journey is readable |
| Knowledge retrieval migration | complete in current worktree | Qdrant Local + FastEmbed adapters, fingerprints and offline citation chain |
| P4.5-6 — Live Smoke And Integrated Acceptance | accepted in current worktree | real smoke, offline gates and desktop/mobile browser acceptance passed |

P4.5-6 acceptance is sufficient for a portfolio checkpoint. Phase 5-8 are
optional follow-on work and require a new explicit authorization.

The current P4.5-6 record is
[Phase 4.5 finalization evidence](verification/phase-4-5-finalization-evidence.md).
The Phase 4.5 portfolio checkpoint is ready. Commit, push, tag, release and
deployment remain separate authorized actions.

The formal knowledge corpus and retrieval-quality evaluation remain unbuilt.
Current knowledge fixtures prove adapter and citation contracts, not measured
retrieval accuracy.

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
- Push, tag, release, and deployment remain separately authorized actions.

## Canonical Documents

- [Repository instructions](../AGENTS.md)
- [Documentation index](README.md)
- [Roadmap](roadmap.md)
- [Product direction decision](adr/0004-product-direction-and-codex-governance.md)
- [Phase 4.5 stage](phases/phase-4-5-research-showcase.md)
- [Phase 4.5 design](superpowers/specs/2026-08-08-phase-4-5-research-showcase-design.md)
- [Phase 4.5 implementation plan](superpowers/plans/2026-08-08-phase-4-5-research-showcase.md)

Historical plans, handoffs, and evidence are not current execution instructions
unless one of the documents above links a specific record for a concrete task.
