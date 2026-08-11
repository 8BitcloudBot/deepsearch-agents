# P4.5-3 DeepAgents Live Research Integration Design

> **Historical design:** This completed package design predates the knowledge
> retrieval migration. Its former provider-specific references are retained
> only as historical context and are superseded by the migration design.

**Status:** Approved design; pending implementation plan

## Scope

P4.5-3 connects the explicit showcase profile to the existing DeepAgents main
agent and expert-worker research shape. The runtime consumes Tavily Web,
read-only MySQL, provenance-bearing knowledge chunks and thread-scoped uploads,
then returns validated P4.5-2 source locators and internal live evidence.

This package does not add report rendering, citation HTTP endpoints, WebSocket
message types or frontend behavior. Those delivery concerns remain P4.5-4.
Automated tests use deterministic fakes and never call a model, Provider,
network or live data source.

## Chosen Architecture

Use a dedicated `ShowcaseResearchRuntime`. Do not add live branches to the
offline `AgentResearchRuntime` or the tutorial runtimes. This keeps the
offline, tutorial and live execution/evidence partitions separate and avoids
conditionals that could change accepted tutorial behavior.

```text
ShowcaseResearchRuntime
  -> opt-in, capability and model gate
  -> DeepAgentsShowcaseExecutor
      -> Web expert tool
      -> MySQL expert tools
      -> knowledge retrieval expert tool
      -> uploaded-file main tool
      -> thread-scoped LiveSourceCollector
  -> validated, deduplicated ShowcaseRunResult
```

The executor is injected through one `ShowcaseAgentExecutor` protocol. The
production adapter wraps a compiled DeepAgents graph. Tests use a deterministic
fake executor that crosses the same interface and records results through the
same collector.

## Runtime Configuration

`ShowcaseRuntimeConfig` owns showcase-only configuration. It first resolves
`SHOWCASE_ENABLED` and `SHOWCASE_SOURCES`. When the exact opt-in is absent, it
must not read model or Provider credential keys. When opt-in is present, it
reads the model configuration and only the credentials needed by explicitly
declared sources.

`Phase2Settings.from_env()` remains unchanged, including its existing rule
that showcase initialization does not read credentials. `app.main` performs
the second, showcase-specific configuration step only for the showcase
profile.

If the model configuration is unavailable, the application still starts. A
showcase task returns a structured `model-unavailable` limitation, performs no
executor or source calls, and never silently relabels offline work as live.

Individual disabled, missing or invalid source configurations become
per-source limitations. Available sources may continue, so partial research
is explicit and useful without fabricating evidence.

## Domain Types

### `LiveEvidence`

An internal, immutable evidence record containing:

- stable `evidence_id`, derived from source ID, locator and quote;
- `source_id` and P4.5 source kind;
- the validated P4.5-2 `{kind, value}` locator;
- a bounded, redacted quote;
- `content_sha256` of the normalized quote;
- optional thread ID, required for uploaded-file evidence.

The evidence type preserves Phase 4 citation concepts without modifying the
frozen Phase 4 fixture contracts, whose source-kind vocabulary is intentionally
different.

### `LiveSourceCollector`

The collector belongs to one thread and accepts only valid `SourceLocator`
instances. It rejects stale, missing, invalid and foreign-thread locators.
It validates the serialized live-source contract, creates `LiveEvidence`, and
deduplicates by stable evidence identity while preserving first-seen order.

The collector also accepts structured `Limitation` values. Messages are
redacted before storage. It has no global registry, filesystem access or
Provider dependency.

### `ShowcaseRunResult`

The runtime result retains `answer` and `artifacts` so it satisfies the
existing runtime interface. It adds immutable `sources`, `evidence` and
`limitations` fields for later P4.5-4 delivery. P4.5-3 returns no new report or
citation artifacts.

## DeepAgents And Source Tools

The production graph keeps the existing orchestration strategy: one main
research coordinator delegates to Web, structured-data and knowledge-base
expert workers. Uploaded-file reading remains a main-agent tool. No competing
strategy, retry framework or recovery subsystem is introduced.

Source tools return bounded summaries to the model and separately record
typed source/evidence through the collector:

- **Tavily Web:** each hit uses its canonical URL, captured time, adapter
  version and bounded content quote.
- **MySQL:** only existing read-only operations are allowed. Result rows are
  mapped to column names. An `id` column is the preferred row identity;
  otherwise a deterministic canonical-row hash is used. Query text is never
  retained in the locator.
- **Knowledge:** the concrete retriever exposes a showcase-only search method that
  preserves SDK message references. Only reference chunks containing dataset,
  document and chunk IDs can produce evidence. Missing reference metadata
  yields a limitation; IDs are never inferred from answer text.
- **Uploaded files:** the tool reads only the current session workspace and
  records the actual artifact basename plus line/character span. Cross-thread
  or absolute filesystem paths are rejected.

Existing Provider protocol methods remain compatible. The knowledge addition is
an additive method on its concrete adapter and does not alter
`KnowledgeProvider.ask()`.

## Failure Semantics

- Missing opt-in or model: no executor or source call; structured limitation.
- Disabled or unconfigured source: no adapter construction or call; structured
  per-source limitation.
- One worker or Provider failure: record a redacted `source-failed`
  limitation, return a safe unavailable message to the main agent, and allow
  other workers to continue.
- Invalid, stale, missing or cross-thread locator: no evidence is created.
- Main DeepAgents execution failure: return a redacted `agent-failed`
  limitation and no raw exception text.
- Runtime code emits no task terminal events. `TaskRegistry` remains the sole
  owner of exactly one `task_completed`, `task_failed` or `task_cancelled`
  event.

Provider raw responses, credentials, absolute paths and unredacted exception
messages must not enter runtime results, events or deterministic fixtures.

## File Responsibilities

- Create `app/showcase/research.py` for live evidence, collector and result
  types.
- Create `app/showcase/runtime.py` for the executor protocol and showcase
  runtime.
- Create `app/showcase/config.py` for fail-closed showcase configuration.
- Create `app/showcase/agent.py` for the dedicated DeepAgents graph assembly.
- Create `app/showcase/source_tools.py` for provenance-recording source tools.
- Modify the knowledge retriever only for additive reference-preserving
  retrieval.
- Modify `app/main.py` only to assemble the showcase runtime.
- Modify `app/showcase/__init__.py` only to export the new public types.
- Add focused P4.5-3 unit and integration tests.

No API schema, WebSocket event type, report renderer, frontend or Phase 4
citation contract file changes are in scope.

## Verification Boundary

Focused tests must prove:

1. four deterministic source outcomes produce four validated live sources and
   evidence records;
2. duplicate outcomes have stable IDs and deduplicate deterministically;
3. one source failure does not prevent the other three from completing;
4. missing model, missing opt-in and disabled capabilities make zero executor
   and source calls;
5. stale, missing and foreign-thread sources produce no evidence;
6. results and limitations contain no secrets, absolute paths or raw errors;
7. execution through `TaskRegistry` still produces exactly one terminal event;
8. tutorial/mock, agent-research, P4.5-1 contracts and P4.5-2 locator tests
   remain unchanged.

The package gate is the focused P4.5-3 tests plus the directly affected
runtime, profile, capability and locator regressions. Full backend, frontend,
release and real-Provider suites remain out of scope.
# Historical Design Notice

This completed package design records the former provider-specific integration.
It was superseded by
`docs/superpowers/specs/2026-08-10-knowledge-retrieval-qdrant-local-fastembed-migration-design.md`
and is excluded from canonical execution context. Provider-specific references
below remain only to preserve the historical design record.
