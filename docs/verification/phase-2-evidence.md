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
| `pytest tests/ -q` | 0 | 185 passed, 10 skipped |
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
