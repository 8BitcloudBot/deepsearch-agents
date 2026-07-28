# ADR 0001: Phase 0 Boundaries

- **Date:** 2026-07-28
- **Status:** Accepted
- **Deciders:** wxhu

## Context

Phase 0 establishes the project infrastructure: Git, Python, frontend, Docker, MySQL, CI, pre-commit, and secret scanning. It explicitly defers all agent business logic, external provider integration, and tutorial implementation to later phases.

## Decision

Phase 0 is **infrastructure-only**:

1. **MySQL** is the only local service dependency, provided via Docker Compose. No other databases, message queues, or external services are started.
2. **All external providers** (LLM, Tavily, RAGFlow) are mocked. No real API keys, calls, or credentials are required or stored.
3. **Persistence strategy** (SQLite vs PostgreSQL) is intentionally undecided. The decision is deferred to Phase 7 per the v3 design.
4. **No agent code** is implemented. DeepAgents, LangGraph, tool integrations, WebSocket, report generation, and tutorial business data are out of scope.
5. **Frontend** is limited to a static shell with no WebSocket, business UI, or chart components.

## Consequences

- Phase 0 produces a clean, testable, buildable skeleton.
- All Phase 1–9 work builds on this foundation.
- Any deviation from this scope is a blocker and must be recorded in `docs/phase-status.md`.
