# Phase 0 Verification Evidence

> 只记录真实执行过的命令和结果。禁止未执行的"通过"。

## Environment

- **OS:** darwin/arm64
- **Repository:** /Users/wxhu/Documents/reasonix/deepsearch-agents
- **Date:** 2026-07-28 04:02 UTC

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
| Node.js | v22.14.0 (standalone binary; .nvmrc=22) |
| pnpm | 11.17.0 (via npx; not globally installed) |
| React | 18.3.1 |
| Vite | 6.4.3 |
| TypeScript | 5.7.3 |
| Docker | 29.4.0 |
| MySQL | 8.0 |

## Commit History (Phase 0 through 0-2)

```
e4761ac docs: establish phase zero-two consistency state
c805a1b chore: refresh secrets baseline timestamp
96dde52 chore: update secrets baseline timestamp
372e34d docs: update changelog with phase zero-one remediation
6a8a611 docs: finalize phase zero acceptance evidence
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

## Phase 0-2 Final Gate Re-execution

All commands executed at 2026-07-28 04:02 UTC. All `.venv/bin/*` paths refer to the project venv.

### 1. Git Status

```bash
$ git status --short
# clean; no untracked or unstaged files
```
Exit 0.

### 2. Git Log

```bash
$ git log --oneline --decorate -12
e4761ac (HEAD -> main) docs: establish phase zero-two consistency state
c805a1b chore: refresh secrets baseline timestamp
...
fe80df8 chore: initialize project governance
```
Exit 0.

### 3. Git Diff Check

```bash
$ git diff --check
# no output
```
Exit 0.

### 4. Python Tests

```bash
$ .venv/bin/python -m pytest tests/ -q
......  [100%]
6 passed in 0.38s
```
Exit 0.

### 5. Ruff Check

```bash
$ .venv/bin/ruff check app tests scripts
All checks passed!
```
Exit 0.

### 6. Ruff Format Check

```bash
$ .venv/bin/ruff format --check app tests scripts
5 files already formatted
```
Exit 0.

### 7. Pre-commit

```bash
$ .venv/bin/pre-commit run --all-files
ruff.....................Passed
ruff-format..............Passed
Detect secrets...........Passed
```
Exit 0.

### 8. Detect Secrets

```bash
$ .venv/bin/detect-secrets scan --baseline .secrets.baseline
# no output
```
Exit 0.

### 9. Frontend Vitest

```bash
$ cd frontend && ./node_modules/.bin/vitest run
✓ src/App.test.tsx (3 tests)
Test Files  1 passed (1)
     Tests  3 passed (3)
```
Exit 0. Node v22.14.0 (standalone binary; host is v25.1.0).

### 10. Frontend ESLint

```bash
$ cd frontend && ./node_modules/.bin/eslint src --ext .ts,.tsx
# no output
```
Exit 0.

### 11. Frontend TypeScript Compile

```bash
$ cd frontend && ./node_modules/.bin/tsc -b
# no output
```
Exit 0.

### 12. Frontend Vite Build

```bash
$ cd frontend && ./node_modules/.bin/vite build
vite v6.4.3 building for production...
✓ built in 359ms
dist/index.html + 2 assets generated.
```
Exit 0.

### 13. Docker Compose Config

```bash
$ docker compose config > /dev/null
```
Exit 0. Valid.

### 14. Doctor Offline

```bash
$ .venv/bin/python scripts/doctor.py --offline
[doctor] Running offline checks ...
  [OK] Python 3.12.7
[doctor] All offline checks passed.
```
Exit 0.

### 15. Doctor MySQL (running, after healthcheck healthy)

```bash
$ docker compose up -d mysql
$ for i in $(seq 1 24); do
    health_state=$(docker inspect --format '{{.State.Health.Status}}' research-copilot-mysql)
    test "$health_state" = healthy && break
    sleep 5
  done
$ test "$health_state" = healthy
$ .venv/bin/python scripts/doctor.py --mysql
```
Health wait detail:
```
health_attempt=1 health_state=starting
health_attempt=2 health_state=healthy
```
Doctor output:
```
[doctor] Running MySQL checks ...
  [OK] phase_0_health table contains 'ok'
[doctor] All MySQL checks passed.
```
Exit 0.

### 16. Doctor MySQL (stopped)

```bash
$ docker compose down
$ .venv/bin/python scripts/doctor.py --mysql
  [FAIL] Cannot connect to MySQL: 2003 (HY000): Can't connect to MySQL server on '127.0.0.1:3306' (61)
[doctor] Is MySQL running? Try: docker compose up -d mysql
```
Exit 3 (non-zero). Actionable error message.

### 17. Phase 1+ Forbidden Scope

```bash
$ grep -rn "DeepAgents\|Tavily\|RAGFlow\|WebSocket\|drug\|medicine" app frontend/src tests docker scripts
```
Exit 1 (no matches). Clean.

---

## Gate Summary

| # | Gate | Exit Code | Result |
|---|------|-----------|--------|
| 1 | git status --short | 0 | clean |
| 2 | git log | 0 | 18 commits |
| 3 | git diff --check | 0 | clean |
| 4 | pytest (6 tests) | 0 | 6 passed |
| 5 | ruff check | 0 | clean |
| 6 | ruff format --check | 0 | 5 formatted |
| 7 | pre-commit run --all-files | 0 | 3/3 passed |
| 8 | detect-secrets scan | 0 | clean |
| 9 | vitest run | 0 | 3 passed |
| 10 | eslint | 0 | clean |
| 11 | tsc -b | 0 | clean |
| 12 | vite build | 0 | dist generated |
| 13 | docker compose config | 0 | valid |
| 14 | doctor --offline | 0 | passed |
| 15 | doctor --mysql (healthy) | 0 | table ok |
| 16 | doctor --mysql (stopped) | 3 | actionable error |
| 17 | forbidden scope check | 1 | clean (no matches) |

**All 17 gates pass with expected exit codes.**

## Known Deviations

| # | Deviation | Reason |
|---|-----------|--------|
| 1 | pnpm via `npx pnpm` | 无全局安装权限 |
| 2 | Node 22 via standalone binary | nvm 未安装；主机 Node v25.1.0 |
| 3 | MySQL doctor requires healthcheck wait | Docker 冷启动延迟 |

## Known Limitations

- MySQL root password (`root`) is a local dev credential; baselined in `.secrets.baseline`.
- pre-commit hooks installed in venv via uv pip; not globally available.
