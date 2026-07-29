# Phase 2 Verification Evidence

## Environment
- **OS:** darwin/arm64 **Date:** 2026-07-29
- **v0.0-deepagents-examples:** `c6c0fa8`
- **MySQL:** `deepsearch-agents-mysql-1:3307`, `tutorial_reader` SELECT-only

## Task 0-2 Commit Sequence (chronological)

| Commit | Message | Gate |
|--------|---------|------|
| `6a5d15a` | `docs: freeze phase two tutorial contracts` | GREEN |
| `c6af299` | `feat: add phase two runtime contracts` | 27 pass |
| `cba9315` | `feat: add tutorial research providers` | 38 pass |
| `624464e` | `test: cover phase two provider contracts` | 9 RED |
| `bd38a60` | `fix: complete phase two provider contracts` | 53 pass |
| `d0eb8ee` | `docs: reconcile phase two provider evidence` | docs |
| `66b33a2` | `style: format external adapter test lines` | format |
| `9b2422b` | `test: require phase two provider remediation fixes` | 8 RED |
| `f1b87bc` | `fix: enforce phase two provider contracts` | GREEN |
| `722fc73` | `fix: reconcile remediation test formatting` | format |

## Round 2 RED Evidence (9b2422b)

```
8 failed: test_success_path_yields_final_message (empty answer),
test_subagents_use_real_tool_objects (string tools not callable),
test_app_profile_only_tutorial (no validation),
test_web/catalog/knowledge (wrong enums),
test_mysql_user_must_be_tutorial_reader (root accepted),
test_semicolon_trailing_rejected (semicolon passed)
```

## Round 2 GREEN Evidence

**149 unit tests pass, 10 skipped, MySQL integration 6 pass, external smoke 2 skip**

### Fixes Applied
1. **RAGFlow generator**: `Session.ask(stream=False)` iterated, `msg.content` extracted, `delete_sessions` in finally
2. **Provider enums**: WEB=mock|tavily, CATALOG=mock|mysql, KNOWLEDGE=mock|ragflow, APP_PROFILE=tutorial only
3. **tutorial_reader enforced**: factory rejects MYSQL_USER=root
4. **Subagents**: `build_tutorial_subagents(web_tools, catalog_tools, knowledge_tools)` accepts callables
5. **execute_readonly**: trailing semicolons rejected
6. **detect-secrets**: baseline regenerated, pre-commit passes without --no-verify
7. **EventBus**: overflow isolation verified, data field accepts JsonValue-compatible dicts
