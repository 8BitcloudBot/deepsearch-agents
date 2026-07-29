# Phase 2 Verification Evidence

## Environment
- **OS:** darwin/arm64 **Date:** 2026-07-29
- **Python:** 3.12, **Pydantic:** 2.13.4

## Event Type Design

```python
# PEP 695 recursive type alias
type JsonValue = (
    None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
)

class TutorialEvent(BaseModel):
    data: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("data", mode="before")
    @classmethod
    def _validate_data(cls, value):
        _validate_json_value_strict(value)  # rejects before Pydantic coercion
        return value
```

**Strict behavior:**
- `bytes`, `bytearray`, `set`, `frozenset`, `tuple`, `object()`, non-string dict keys → **REJECTED** (ValidationError)
- Field-level `mode="before"` validator prevents Pydantic default coercion
- JSON Schema contains `$defs/JsonValue` with recursive references
- `data.additionalProperties.$ref` → `#/$defs/JsonValue`

## Final Gate

| Gate | Exit | Result |
|------|------|--------|
| `pytest tests/ -q` | 0 | 187 passed, 10 skipped |
| `ruff check` | 0 | clean |
| `ruff format --check` | 0 | all formatted |
| `pre-commit run --all-files` | 0 | 3/3 passed |
| `docker compose config` | 0 | valid |
| `git diff --check` | 0 | clean |
| MySQL integration (`PHASE2_MYSQL_INTEGRATION=1`) | 0 | 6 passed |

## Direct Rejection Evidence
```
bytes     → REJECTED (ValidationError)
set       → REJECTED (ValidationError)
tuple     → REJECTED (ValidationError)
object    → REJECTED (ValidationError)
non-str key → REJECTED (ValidationError)
```

## Known Limitations
- `b"x"` inside a dict key → rejected at field_validator level
- `.secrets.baseline` unchanged
- Task 3 remains blocked

## Task 4: Agent Factory & Runtimes

**Date:** 2026-07-29

### RED Phase
- Wrote 4 test files (24 tests total) all failing on import — modules did not exist.

### Implementation
- `app/agent/factory.py`: `create_tutorial_agent(model, bundle, events)` — assembles DeepAgents graph:
  - Creates web/catalog/knowledge tool sets from ProviderBundle
  - Builds 3 subagents via `build_tutorial_subagents`
  - Creates main-level tools: `read_uploaded_file`, `generate_markdown_report_tool`, `generate_pdf_report_tool`
  - Calls `create_deep_agent()` with: injected model, MAIN_PROMPT, main tools, subagents, InMemorySaver, name "tutorial-research-agent"
  - All tools use `RunnableConfig.configurable.thread_id` for event routing

- `app/agent/runtime.py`: Value objects + two runtimes behind TutorialRuntime protocol:
  - `RuntimeRequest(query, context)` / `RuntimeResult(answer, artifacts)` frozen dataclasses
  - `TutorialRuntime` Protocol: `async def run(request) -> RuntimeResult`
  - `MockTutorialRuntime(bundle, events)`: Deterministic fixed sequence through all 3 providers, reads uploaded .md fixtures, generates both reports, emits paired agent/tool + artifact events, NEVER emits task lifecycle/terminal events
  - `DeepAgentsTutorialRuntime(graph, bundle, events)`: Real `agent.astream()` with stream_mode="updates", normalizes agent/tool events from stream chunks, generates reports, resets session_context

### GREEN Phase
```bash
.venv/bin/python -m pytest tests/unit/phase2/test_agent_factory.py \
  tests/unit/phase2/test_runtime_events.py \
  tests/integration/phase2/test_mock_runtime.py -q
# 24 passed

.venv/bin/python -m pytest tests/integration/phase2/test_real_model_smoke.py -q
# 1 skipped (no MODEL_API_KEY — correct skip behavior)

.venv/bin/ruff check app/agent tests/unit/phase2 tests/integration/phase2
# All checks passed

.venv/bin/ruff format --check app/agent tests/unit/phase2 tests/integration/phase2
# 26 files already formatted

.venv/bin/python -m pytest tests/ -q
# 238 passed, 11 skipped
```
