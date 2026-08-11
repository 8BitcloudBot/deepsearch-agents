# Deepsearch Repository Instructions

## Canonical Context

Read only these documents by default, in order:

1. `docs/README.md`
2. `docs/phase-status.md`
3. `docs/roadmap.md`
4. `docs/phases/phase-4-5-research-showcase.md`
5. `docs/superpowers/plans/2026-08-08-phase-4-5-research-showcase.md`

Do not preload `docs/handoffs/`, historical plans/specs, or verification evidence.
Read them only when the user asks for historical analysis or a current canonical
document links a specific record for a concrete reason.

## Product Direction

This project remains a multi-source DeepAgents research product. Its primary
flow is:

`research request -> main agent and expert workers -> Tavily/MySQL/local knowledge retrieval/uploads -> validated citations -> API/WebSocket/React -> Markdown/PDF`

Evaluation runners, deterministic fixtures, fingerprints, and citation metrics
prove the product's behavior. They must not replace the research workflow as
the primary user experience.

Phase 4.5 is the only active development stage. P4.5-1 through P4.5-5 are
implemented in the current worktree. P4.5-6 and the Phase 4.5 portfolio
checkpoint are accepted in the current worktree; Git closeout remains a
separate authorization.
Phases 5-8 are optional follow-on work requiring explicit user authorization.

## Execution Rules

- Use the current Codex session only. Do not invoke Reasonix, use DeepSeek as a
  coding worker, dispatch subagents, or delegate implementation to another
  model unless the user explicitly changes this rule.
- Product-level DeepSeek/provider configuration and DeepAgents `SubAgent`
  concepts are runtime concerns, not coding-worker authorization.
- Implement one bounded package at a time and preserve the existing framework,
  API, event, security, and artifact contracts.
- Real providers, live data sources, production data, push, tag, release, and
  deployment require separate explicit authorization.
- Do not restore deleted collaboration worktrees, plans, or unaccepted partial
  changes from reflog or historical sessions.

## Verification Policy

Choose the smallest gate that proves the changed behavior:

1. Local change: focused tests at the nearest ownership boundary plus checks on
   touched files.
2. Cross-module contract: add the directly affected API, integration, or
   frontend contract tests.
3. Package acceptance: run the package's affected backend/frontend regression
   surface and relevant smoke checks.
4. CI or release: run the complete offline backend, frontend, static, security,
   and reproducibility gates.

Do not repeat the same internal assertion across multiple layers without a
distinct failure mode. Do not run the full suite after every small edit.

## Documentation

- `docs/phase-status.md` contains current facts only.
- Exact command output and test counts belong in one package evidence record,
  not in every long-lived status document.
- Historical plans, handoffs, and evidence retain their original wording and
  are never current execution instructions.
