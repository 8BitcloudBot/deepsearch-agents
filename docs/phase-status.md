# Phase Status

## Current Phase

- **Phase:** 2 — Tutorial Parity
- **Status:** `in_progress`
- **Started:** 2026-07-29
- **Target Tag:** `v0.1-tutorial-parity`（用户验收通过后创建）

## Phase 2 Task Progress

| Task | Name | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 0 | Freeze Contracts | completed | `6a5d15a` | ADR 0003, deps locked |
| 1 | Settings/Events/Mocks | completed | `c6af299` | 27 tests |
| 2 | Providers+Tools+SQL | completed | `cba9315` | factory, tools, subagents, SQL policy |
| R1 | RED: Provider Contracts | completed | `624464e` | 9 RED failures |
| F1 | Fix: Provider Contracts | completed | `bd38a60` | RAGFlow 0.26.0, SQL validation |
| R2 | RED: Remediation 2 | completed | `9b2422b` | 8 RED failures |
| F2 | Fix: Remediation 2 | completed | `f1b87bc` | generator, enums, tutorial_reader, semicolons |
| 3 | Workspace & Reports | pending | — | — |
| 4 | Agent & Runtimes | pending | — | — |
| 5 | FastAPI/WebSocket | pending | — | — |
| 6 | React Workbench | pending | — | — |
| 7 | Document & Verify | pending | — | — |

## Blockers

None.

## Key Remediation Results (Round 2)

- RAGFlow `Session.ask(stream=False)`: generator iterated, `Message.content` extracted, `delete_sessions` in finally (success + error)
- WEB=tavily/mock, CATALOG=mysql/mock, KNOWLEDGE=ragflow/mock per-provider enums
- APP_PROFILE only "tutorial"
- MySQL provider enforces `tutorial_reader`, rejects `root`
- `execute_readonly`: trailing semicolons rejected, limit clamped 1..1000
- Subagents: `build_tutorial_subagents(web_tools, catalog_tools, knowledge_tools)` accepts real callables
- detect-secrets pre-commit: baseline regenerated, all known test secrets baselined
- 149 unit tests pass, 6 MySQL integration pass, 2 external smoke skip
