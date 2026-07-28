# Phase 0 Verification Evidence

> 只记录真实执行过的命令和结果。未执行的检查不写入"通过"。

## Environment

- **OS:** darwin/arm64
- **Repository:** /Users/wxhu/Documents/reasonix/deepsearch-agents
- **Date:** 2026-07-28 03:48 UTC

## Versions

| Tool | Version |
|------|---------|
| Python | 3.12.7 |
| uv | 0.11.7 |
| FastAPI | 0.140.7 |
| uvicorn | 0.51.0 |
| pytest | 8.4.2 |
| ruff | 0.16.0 |
| mysql-connector-python | 9.7.0 |
| pre-commit | 4.6.1 |
| detect-secrets | 1.5.0 |
| Node.js | v22.14.0 (verified with .nvmrc=22) |
| pnpm | 11.17.0 (via npx) |
| React | 18.3.1 |
| Vite | 6.4.3 |
| TypeScript | 5.7.3 |
| Docker | 29.4.0 |
| MySQL | 8.0 |

## Commit History (Phase 0-1)

```
0b352a7 docs: add project design and implementation plans
c86e53f chore: verify frontend with pinned node 22
d5ea849 ci: complete phase zero local hooks
a6267a9 fix: verify mysql doctor against health table
0d724c0 style: format phase zero doctor
8fcbb42 docs: establish phase zero-one remediation state
e78aa7b docs: set phase zero status to awaiting_user_acceptance
0ef89c8 docs: record phase zero verification
ae13286 ci: enforce phase zero verification
e5dab66 chore: add local mysql health dependency
e9aae8c feat: add phase zero frontend shell
1ae249d feat: add phase zero api health contract
fe80df8 chore: initialize project governance
```

---

## Final Gate Checklist

### 1. git status

```bash
$ git status --short
 M docs/phase-status.md   # (only the status update in progress)
```
Exit 0. Worktree clean except for in-progress status update.

### 2. Python Tests

```bash
$ .venv/bin/python -m pytest tests/ -q
......  [100%]
6 passed in 0.42s
```
Exit 0. All 6 tests pass.

### 3. Ruff Check

```bash
$ .venv/bin/ruff check app tests scripts
All checks passed!
```
Exit 0.

### 4. Ruff Format

```bash
$ .venv/bin/ruff format --check app tests scripts
5 files already formatted
```
Exit 0.

### 5. Frontend Tests

```bash
$ npx pnpm --dir frontend exec vitest run
✓ src/App.test.tsx (3 tests)
Test Files  1 passed (1)
     Tests  3 passed (3)
```
Exit 0. Node v22.14.0 used.

### 6. Frontend Lint

```bash
$ npx pnpm --dir frontend lint
```
Exit 0. No output = clean.

### 7. Frontend Build

```bash
$ npx pnpm --dir frontend build
vite v6.4.3 building for production...
✓ built in 378ms
dist/index.html + 2 assets generated.
```
Exit 0.

### 8. Docker Compose Config

```bash
$ docker compose config > /dev/null
```
Exit 0. Valid config.

### 9. Doctor Offline

```bash
$ .venv/bin/python scripts/doctor.py --offline
[doctor] Running offline checks ...
  [OK] Python 3.12.7
[doctor] All offline checks passed.
```
Exit 0.

### 10. Doctor MySQL (running)

```bash
$ .venv/bin/python scripts/doctor.py --mysql
[doctor] Running MySQL checks ...
  [OK] phase_0_health table contains 'ok'
[doctor] All MySQL checks passed.
```
Exit 0.

### 11. Doctor MySQL (stopped)

```bash
$ docker compose down mysql
$ .venv/bin/python scripts/doctor.py --mysql
  [FAIL] Cannot connect to MySQL: 2003: Can't connect to MySQL server on '127.0.0.1:3306' (61)
[doctor] Is MySQL running? Try: docker compose up -d mysql
```
Exit 3 (non-zero). Actionable error message shown.

### 12. Pre-commit (second run)

```bash
$ .venv/bin/pre-commit run --all-files
ruff.....................Passed
ruff-format..............Passed
Detect secrets...........Passed
```
Exit 0. Second consecutive run also exits 0.

### 13. Detect Secrets Scan

```bash
$ .venv/bin/detect-secrets scan --baseline .secrets.baseline
```
Exit 0. No un-baselined secrets detected.

### 14. Phase 1+ Forbidden Scope

```bash
$ grep -rn "DeepAgents\|Tavily\|RAGFlow\|WebSocket\|drug\|medicine" app frontend/src tests docker scripts
```
Exit 1 (no matches). Clean — no Phase 1+ code.

---

## Known Limitations

1. **pnpm** not globally installed; invoked via `npx pnpm`.
2. **nvm** not installed; Node 22 verified with standalone binary.
3. **MySQL root password** (`root`) is a local dev credential in docker-compose.yml; baselined in `.secrets.baseline`.
4. Node on host is v25.1.0; frontend tests verified with v22.14.0 per .nvmrc.

## Phase 0-1 Gate Result

**PASSED.** All 14 gate items return expected exit codes. MySQL doctor passes when running (exit 0) and fails when stopped (exit 3). Pre-commit and detect-secrets hooks execute and pass. No Phase 1+ content in source.
