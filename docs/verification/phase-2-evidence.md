# Phase 2 Verification Evidence

## Environment
- **OS:** darwin/arm64 **Date:** 2026-07-29
- **v0.0-deepagents-examples:** `c6c0fa8`

## Phase 2-n2 Commits

| Commit | Message | Task |
|--------|---------|------|
| `6e79fa6` | `fix: expose recursive json event annotations` | T1 |
| `5df1ac5` | `test: remove phase two false green remediation cases` | T2 |
| `08630a4` | `test: assert exact tutorial subagent contracts` | T3 |
| `3e614ec` | `fix: remove any from event type exposure` | — |
| `7ab3186` | `docs: reconcile phase two remediation evidence` | T4 |

## Final Gate Results

| Gate | Exit | Result |
|------|------|--------|
| `pytest tests/ -q` | 0 | 167 passed, 10 skipped |
| `ruff check` | 0 | clean |
| `ruff format --check` | 0 | 45 formatted |
| `pre-commit run --all-files` | 0 | 3/3 passed |
| `docker compose config` | 0 | valid |
| `git diff --check` | 0 | clean |
| MySQL integration | 0 | 6 passed |

## Event Type Design

```python
# PEP 695 recursive type alias (Python 3.12 + Pydantic 2.13.4)
type JsonValue = (
    None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
)

class TutorialEvent(BaseModel):
    data: dict[str, JsonValue] = Field(default_factory=dict)

def emit(self, ...,
         data: dict[str, JsonValue] | None = None) -> TutorialEvent
```

Pydantic generates a `$defs/JsonValue` entry in the JSON Schema
and rejects `object()` and non-string dict keys at construction time.
`bytes`, `set`, and `tuple` are coerced by Pydantic's default mode.
