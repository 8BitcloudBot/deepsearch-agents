# ADR 0002: DeepAgents Version and API Surface

- **Date:** 2026-07-28
- **Status:** Accepted
- **Deciders:** wxhu

## Context

Phase 1 requires DeepAgents capability examples. The API surface must be introspected from the actual installed packages, not guessed from memory or tutorial documentation.

## Decision

### Exact Versions

| Package | Version |
|---------|---------|
| deepagents | 0.6.12 |
| langgraph | 1.2.9 |
| langchain-core | 1.5.1 |
| langchain-openai | 1.4.1 |
| langchain | 1.3.14 |
| langgraph-checkpoint | 4.1.1 |
| langgraph-prebuilt | 1.1.0 |

### create_deep_agent Signature

```python
create_deep_agent(
    model: str | BaseChatModel | None = None,
    tools: Sequence[BaseTool | Callable | dict] | None = None,
    system_prompt: str | SystemMessage | None = None,
    middleware: Sequence[AgentMiddleware] = (),
    subagents: Sequence[SubAgent | CompiledSubAgent | AsyncSubAgent] | None = None,
    skills: list[str] | None = None,
    memory: list[str] | None = None,
    permissions: list[FilesystemPermission] | None = None,
    backend: BackendProtocol | BackendFactory | None = None,
    interrupt_on: dict[str, bool | InterruptOnConfig] | None = None,
    response_format: ... | None = None,
    state_schema: type[DeepAgentState] | None = None,
    context_schema: type[ContextT] | None = None,
    checkpointer: None | bool | BaseCheckpointSaver = None,
    store: BaseStore | None = None,
    debug: bool = False,
    name: str | None = None,
    cache: BaseCache | None = None,
) -> CompiledStateGraph
```

### SubAgent (TypedDict)

Required: `name`, `description`, `system_prompt`.
Optional: `tools`, `model`, `middleware`, `interrupt_on`, `skills`, `permissions`, `response_format`.

### CompiledSubAgent (TypedDict)

Required: `name`, `description`, `runnable` (a LangChain Runnable).

### Key Public API Used in Phase 1

- `create_deep_agent` — main agent factory
- `SubAgent` — declarative dictionary sub-agent
- `CompiledSubAgent` — LangGraph/Runnable sub-agent wrapper
- `MemorySaver` — in-memory checkpointer for interrupt/resume
- `interrupt()` — LangGraph human-in-the-loop
- `Command(resume=...)` — resume after interrupt
- `BackendProtocol` — filesystem backend interface
- `Store` / `BaseStore` — cross-invocation key-value storage
- `AgentMiddleware` — middleware hook interface

### Tutorial Name Mapping

The original tutorial references concepts that map to:

| Tutorial Term | Current API |
|---------------|-------------|
| "子智能体" (sub-agent) | `SubAgent` TypedDict |
| "工具调用" (tool call) | Built-in tools from `create_deep_agent` |
| "中断/恢复" (interrupt/resume) | LangGraph `interrupt()` + `Command(resume=...)` |
| "memory" | `MemoryMiddleware` config via `memory` param |
| "store" | `store` param accepting `BaseStore` |
| "skills" | `skills` param + `SkillsMiddleware` |

### Deprecated or Nonexistent APIs

None identified at inspection time. All APIs tested via `inspect.signature()` and `get_type_hints()`. If any tutorial API is missing from current version, this ADR will be updated with the blocking issue.

### Mock/Offline Strategy

- All unit tests use mock LLM (FakeListChatModel or equivalent)
- Real model smoke tests gated behind `MODEL_API_KEY` env var
- No external API calls in offline tests

### Phase 2 Allowable Reuse

Phase 2 may reuse: settings loading, event normalization, runner pattern, API signatures recorded here. Phase 2 must NOT copy tutorial source code verbatim.

## Consequences

- All Phase 1 examples use these exact APIs
- Any API mismatch discovered during implementation must be recorded as blocker
- Version changes require ADR update and re-introspection
