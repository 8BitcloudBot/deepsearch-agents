# Phase Status

## Current Phase
- **Phase:** 2 — Tutorial Parity
- **Status:** `awaiting_user_acceptance`
- **Target Tag:** `v0.1-tutorial-parity`（用户验收通过后创建）

## Phase 2-n Remediation

| Task | Name | Commit | Notes |
|------|------|--------|-------|
| 0 | Rejection baseline | `1bb001b` | scope frozen, blockers listed |
| 1 | Thread-aware tool events | `6d19d98` | all 7 tools use RunnableConfig, paired events |
| 2 | Recursive JsonValue | `0f5ffcd` | validate at emit boundary |
| 3 | Overflow isolation | (included in 2) | 257-event test drains one sub, proves single overflow |
| 4 | SQL limit 1..100 | `1b2f5f0` | `_clamp_limit` replaces 1000 |
| 5 | Subagent tool sets | `d7f9d9e` | exact names/prompts/tools tested |
| 6 | Final gate | `3020273` | 159 pass, ruff clean |

## Blockers

**None.** All 6 items resolved.

## Tests
- Unit: 159 passed
- Integration: 8 skipped (no MODEL_API_KEY), 2 skipped (no external config)
- MySQL: 6 passed (PHASE2_MYSQL_INTEGRATION=1)
