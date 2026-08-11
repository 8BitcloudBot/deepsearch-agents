# ADR 0003: Phase 2 Tutorial Contracts

> **Historical background:** This accepted tutorial contract records the
> pre-migration provider vocabulary. It is retained for audit only and is not
> current execution guidance; current direction is defined by
> `docs/phase-status.md`.

- **Date:** 2026-07-29
- **Status:** Accepted
- **Deciders:** wxhu

## Context

Phase 2 implements the tutorial baseline (chapters 8-14). It requires provider
abstractions, a concrete event bus, two runtimes (mock and real), FastAPI/WebSocket,
and a React workbench — all on top of Phase 1's locked DeepAgents 0.6.12.

## Decision

### Explicit Provider Modes

Every external dependency is behind a Protocol. The `ProviderBundle` carries both
the concrete adapter and an explicit mode field (`"mock"|"tavily"`, `"mock"|"mysql"`,
`"mock"|"ragflow"`). Real adapters are lazy — never constructed during module import.
Provider provenance is determined only from mode fields, never `isinstance()`.

### Concrete InMemoryEventBus (No Abstraction)

Phase 2 uses exactly one concrete `InMemoryEventBus`. No `EventSink`/`EventSource`
protocols. It provides per-thread monotonic sequences, bounded live-only subscriptions
(256 events), and overflow detection. No history, replay, or persistence.

### Task Lifecycle Ownership

`TaskRegistry` alone emits `task_started` and exactly one of `task_completed`,
`task_cancelled`, or `task_failed`. Runtimes never emit task lifecycle events.

### Single SessionContext

One `ContextVar[SessionContext]` per thread. `RuntimeRequest` carries `query + context`
only; thread_id/workspace come from `context`.

### Memory-Only State

Tasks and events live in memory only. No persistence, replay, or recovery in Phase 2.

### SELECT-Only MySQL

Two-layer defense: sqlglot validates read-only SQL AST; application connects as
`tutorial_reader` with `SELECT` only on `research_copilot.*`. Root account is
bootstrap-only.

### Relative Artifact Paths

All artifact paths are relative to `output/session_<thread_id>/`. Client never
sends or receives absolute server paths.

### Heartbeat Separation

`{type:"pong"}` is a separate heartbeat message, not a `TutorialEvent`.

### Installed Provider Versions

| Package | Version |
|---------|---------|
| deepagents | 0.6.12 |
| langgraph | 1.2.9 |
| langchain-core | 1.5.1 |
| langchain-openai | 1.4.1 |
| tavily-python | 0.7.26 |
| ragflow-sdk | 0.26.0 |
| sqlglot | 29.0.1 |
| pypdf | 6.14.2 |
| python-docx | 1.2.0 |
| openpyxl | 3.1.5 |
| reportlab | 4.5.1 |
| httpx | 0.28.1 |

### API Introspection

- `RAGFlow(api_key, base_url, version='v1')` — methods: `list_chats`, `create_chat`, `delete_chats`, `get_recent_messages`
- `TavilyClient(api_key, ...)` — `search(query, max_results=..., ...) -> dict`
- `create_deep_agent(model, tools, system_prompt, middleware, subagents, ...)` — 18 params

## Consequences

- Tutorial chapter 8-14 mapped to Tasks 0-7
- All offline tests use deterministic mock providers
- Real-service smoke gated behind explicit opt-in env vars
- MySQL volume preserved; bootstrap idempotent via SQL script
