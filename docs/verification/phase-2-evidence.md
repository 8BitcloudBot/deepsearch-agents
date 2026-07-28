# Phase 2 Verification Evidence

## Environment
- **OS:** darwin/arm64
- **Date:** 2026-07-29
- **v0.0-deepagents-examples:** `c6c0fa8`
- **Node:** v22.14.0 (standalone)

## Task 0: Freeze Contracts
- **RED:** `import docx,...` → ModuleNotFoundError
- **GREEN:** all imports pass, 83 tests pass
- **Commit:** `6a5d15a`

## Task 1: Runtime Contracts
- **RED:** 3 import errors (modules missing)
- **GREEN:** 27 passed
- **Commit:** `c6af299`

## Task 2: Research Providers
- **Commit:** `cba9315`
- **SQL policy:** 15 passed (valid SELECT, WITH, rejects INSERT/DELETE/comments/LOAD_FILE/FOR UPDATE/CALL/cross-db/multi-statement)

## Task 2-R: Provider Contract RED
- **RED:** 9 failures (factory missing, patch targets wrong, LOAD_FILE+comment not rejected)
- **Commit:** `624464e`

## Task 2-F: Provider Contract Fixes
- **GREEN:** 53 passed
- **MySQL integration:** 6 passed (PHASE2_MYSQL_INTEGRATION=1)
- **External smoke:** 2 skipped (no config)
- **Commit:** `bd38a60`

## MySQL Preserved-Volume Bootstrap
- Container: `deepsearch-agents-mysql-1`, port 3307
- `tutorial_reader` SELECT-only confirmed
- `INSERT` rejected at DB level → row count unchanged (3)

## SQL Policy Coverage
- Accepted: `SELECT *`, `SELECT with WHERE`, `WITH ... SELECT`, `SELECT COUNT`
- Rejected: INSERT/DELETE/UPDATE/CREATE/DROP/ALTER/CALL/LOAD_FILE/FOR UPDATE/cross-db/multi-statement/comments
- Table names validated against `[A-Za-z_][A-Za-z0-9_]*`
- All limits clamped to 1..100 (preview) or 1..1000 (execute)

## RAGFlow 0.26.0 API
- `list_chats()` → `list[Chat]`
- `Chat.name`, `Chat.description`, `Chat.knowledge_bases`
- `Chat.create_session()` → `Session`
- `Session.ask(question, stream=False)` → answer
- `Chat.delete_sessions([session.id])` in finally
