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

## Event Type Design (Final)

```python
# Public emit signature uses JsonValue
def emit(self, thread_id, event_type, message,
         data: dict[str, "JsonValue"] | None = None) -> TutorialEvent

# Pydantic model uses dict[str, Any] + model_validator
# (recursive types unsupported in Pydantic 2.13)
class TutorialEvent(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_data(self):
        _validate_json_value(self.data)  # rejects objects, bytes, sets, tuples, non-string keys
        return self
```

## Known Limitations
- `TutorialEvent.data` Pydantic field is `dict[str, Any]` due to recursive type limitation; runtime enforcement via `model_validator`
- `InMemoryEventBus.emit` parameter typed as `dict[str, "JsonValue"] | None`
- Task 3 blocked until Phase 2 user acceptance
- `.secrets.baseline` unchanged from accepted fixed point
