# Phase 2 Verification Evidence

## Environment
- **OS:** darwin/arm64 **Date:** 2026-07-29
- **v0.0-deepagents-examples:** `c6c0fa8`

## Phase 2-n2 Remediation Commits

| Commit | Message | Task |
|--------|---------|------|
| `6e79fa6` | `fix: expose recursive json event annotations` | T1 |
| `5df1ac5` | `test: remove phase two false green remediation cases` | T2 |
| `08630a4` | `test: assert exact tutorial subagent contracts` | T3 |

## Final Gate Results

| Gate | Command | Exit | Result |
|------|---------|------|--------|
| Full pytest | `pytest tests/ -q` | 0 | 159 passed, 10 skipped |
| Phase 2 pytest | `pytest tests/unit/phase2 tests/integration/phase2 -q` | 0 | all pass |
| MySQL integration | `PHASE2_MYSQL_INTEGRATION=1 pytest ...` | 0 | 6 passed |
| Ruff check | `ruff check app tests` | 0 | clean |
| Ruff format | `ruff format --check app tests` | 0 | clean |
| Pre-commit | `pre-commit run --all-files` | 0 | 3/3 passed |
| Docker Compose | `docker compose config` | 0 | valid |
| Git diff check | `git diff --check` | 0 | clean |

## Secrets Baseline
- `.secrets.baseline` unchanged from accepted fixed point.
- `.venv/bin/pre-commit run --all-files` passed without mutating the baseline.

## Known Limitations
- `dict[str, Any]` in Pydantic model uses `BeforeValidator` with `_validate_json_value` (recursive types unsupported by Pydantic)
- No MODEL_API_KEY: invoke/stream real model smoke not executed
- External Tavily/RAGFlow smoke: skipped (no config)
- Task 3 remains blocked
