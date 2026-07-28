# Phase 1 Verification Evidence

> 只记录真实执行过的命令和结果。Phase 1 + 1-1 完整记录。

## Environment

- **OS:** darwin/arm64
- **Repository:** /Users/wxhu/Documents/reasonix/deepsearch-agents
- **Date:** 2026-07-28
- **v0.0-foundation:** tag exists, points to `9715255`

## Exact Dependency Versions

| Package | Version |
|---------|---------|
| deepagents | 0.6.12 |
| langgraph | 1.2.9 |
| langchain-core | 1.5.1 |
| langchain-openai | 1.4.1 |
| langgraph-checkpoint | 4.1.1 |
| langgraph-prebuilt | 1.1.0 |

## API Introspection Summary

- `create_deep_agent`: model/tools/system_prompt/middleware/subagents/skills/memory/permissions/backend/interrupt_on/checkpointer/store/debug/name/cache
- `SubAgent` (TypedDict): name/description/system_prompt + optional tools/model/middleware/interrupt_on/skills/permissions/response_format
- `CompiledSubAgent` (TypedDict): name/description/runnable
- `FilesystemBackend(root_dir, virtual_mode, max_file_size_mb)`: write/read/ls/glob/grep
- `InMemoryStore()`: put/get/search
- `MemoryMiddleware(backend, sources, add_cache_control)`
- `SkillsMiddleware(backend, sources)`: state_schema=SkillsState with skills_metadata
- `AgentMiddleware.wrap_model_call(request, handler)`
- `interrupt()` / `Command(resume=...)` / `MemorySaver`

## Commit History

```
7762a13 test: verify phase one interrupt behavior
e9a97b6 feat: implement real backend store and memory examples
fb66f5c feat: add observable middleware and real skills loading
eeb3ca9 test: strengthen phase one example contracts
```

## Final Gate Results (2026-07-28)

### 1. git status --short
```
# clean
```
Exit 0.

### 2. Unit Tests
```
77 passed in 4.18s
```
Exit 0.

### 3. Integration Tests
```
2 skipped in 0.01s
```
Exit 0. MODEL_API_KEY not set.

### 4. Ruff Check
```
All checks passed!
```
Exit 0.

### 5. Ruff Format Check
```
33 files already formatted
```
Exit 0.

### 6. Pre-commit (2nd run)
```
ruff.....................Passed
ruff-format..............Passed
Detect secrets...........Passed
```
Exit 0.

### 7. Detect Secrets
```
detect-secrets exit=0
```

### 8. Runner --list
All 7 examples listed correctly.

### 9. Offline Examples (no MODEL_API_KEY)
| Example | Exit Code |
|---------|-----------|
| interrupt-resume | 0 |
| backend-store-memory | 0 |
| middleware-skills | 0 |

### 10. Model Examples (no MODEL_API_KEY)
| Example | Exit Code |
|---------|-----------|
| invoke | 3 |
| stream | 3 |

### 11. Forbidden Scope
```
examples/phase1/README.md:60 — documentation line (not implementation)
```
Clean.

### 12. git diff --check
Clean.

## Behavioral Test Results

### Interrupt/Resume (6 tests)
- First run exposes interrupt payload ✅
- Approve executes risk action once ✅
- Reject does not execute ✅
- Thread isolation ✅
- Repeated resume idempotent ✅
- Runs without API key ✅

### Backend/Store/Memory (9 tests)
- Real FilesystemBackend ✅
- Write/read within root ✅
- Path escape rejected ✅
- Real InMemoryStore ✅
- Namespace isolation ✅
- Real MemoryMiddleware ✅
- Memory visible to same thread ✅
- Memory isolated between threads ✅
- Temp path cleanup ✅

### Middleware/Skills (7 tests)
- Successful call records metadata ✅
- Handler error records error_type ✅
- No prompt/key leaked ✅
- Deterministic clock ✅
- Request ID factory used ✅
- source-review skill discovered ✅
- Missing skill dir handles gracefully ✅

## Total Tests

- **Unit**: 77 passed
- **Integration**: 2 skipped (MODEL_API_KEY not set)
- **Real model smoke**: NOT executed (no key)

## Known Limitations

- No MODEL_API_KEY: invoke/stream/dictionary-subagents/runnable-subagent cannot run real model
- Integration smoke correctly skips
- SkillsMiddleware skills_metadata requires full LangGraph runtime to populate; discovery verified via source_labels and directory listing of SKILL.md
- Node 22 required per .nvmrc but host has v25.1.0
