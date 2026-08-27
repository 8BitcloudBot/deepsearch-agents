# Schema 5.0 Quality Optimization Evidence

**Date:** 2026-08-16

**Scope:** Balanced-mode retrieval concurrency, coverage fast path, cited-only evidence delivery, cumulative Markdown deduplication, frontend evidence presentation, runtime capabilities, and startup configuration.

## Offline Gates

- Backend: `741 passed, 4 skipped`; one existing Starlette/httpx deprecation warning.
- Ruff: passed.
- Frontend Vitest: `9 passed`.
- TypeScript, ESLint, Vite production build, and `git diff --check`: passed.

## Authorized Live Acceptance

- Runtime capabilities: model, knowledge, Web, and session files all reported `ready`.
- Ten sequential turns: `10/10` completed.
- Source combinations: four knowledge-only turns, three knowledge + Web turns, and three knowledge + session file + Web turns.
- Every claim reference resolved to retained evidence; each turn delivered at most six cited evidence items.
- Total wall time: `289.4s`; slowest turn: `42.49s`.
- Artifact: `research-report.md` only.
- Ten-turn report: `37,205` bytes, one cumulative evidence appendix, no internal synthesis fields or JSON code fence.

The live run exposed concurrent access failure when two queries used the same Qdrant Local instance. A regression test now keeps source groups concurrent and Web queries concurrent while serializing queries within the local knowledge adapter boundary. A focused live rerun then completed in `16.94s` with knowledge evidence and no retrieval limitation.

A focused security rerun completed with knowledge, session-file, and Web evidence, used the required phrase “仅按允许列表执行”, and did not use the rejected synonym in answer or claim text.

## Browser Checks

- Desktop `1280x720`: no horizontal overflow, no duplicate evidence anchors, four-line quote clamp and expand/collapse interaction verified.
- Mobile `375x812`: no horizontal overflow; title actions remain readable without wrapping; composer and evidence layout remained within viewport width.

No commit, push, release, publication, deployment, MySQL connection, PDF artifact, or JSON download was produced.
