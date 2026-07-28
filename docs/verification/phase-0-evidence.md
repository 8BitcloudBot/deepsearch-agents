# Phase 0 Verification Evidence

> 验收证据记录。记录真实执行的命令、时间、环境、退出码、输出摘要和失败场景。

## Environment

- **OS:** darwin/arm64
- **Repository:** /Users/wxhu/Documents/reasonix/deepsearch-agents
- **Date:** 2026-07-28

---

## Task 0: Git and Documentation Contract

### Verification

| Item | Result |
|------|--------|
| `pwd` equals repo path | `/Users/wxhu/Documents/reasonix/deepsearch-agents` |
| `git init -b main` | Exit 0, new repository on `main` |
| `git config core.autocrlf input` | Exit 0 |
| `.gitignore` rules verified | `.env`, `.venv`, `node_modules`, `output/report.md` all ignored |
| `git diff --check` clean | Exit 0, no whitespace errors |
| Commit created | `fe80df8` — `chore: initialize project governance` |

---

## Task 1: Python Health Contract

### Verification

| Item | Result |
|------|--------|
| Python version | 3.12.7 |
| uv version | 0.11.7 |
| FastAPI version | 0.140.7 |
| uvicorn version | 0.51.0 |
| pytest version | 8.4.2 |
| httpx version | 0.28.1 |
| ruff version | 0.16.0 |
| `uv sync --extra dev` | Exit 0, 51 packages resolved |
| `pytest tests/unit/test_health.py -q` | 3 passed in 0.76s |
| `ruff check app tests` | All checks passed |
| `curl /health` response | `{"status":"ok","service":"research-copilot-api","phase":"0"}` |
| HTTP status | 200 OK |

### Commands Executed

```bash
uv sync --extra dev
.venv/bin/python -m pytest tests/unit/test_health.py -q
.venv/bin/ruff check app tests
.venv/bin/uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
curl -fsS http://127.0.0.1:8000/health
```

---

## Task 2: React/Vite Frontend Skeleton

### Verification

| Item | Result |
|------|--------|
| Node version | v25.1.0 |
| pnpm version | 11.17.0 (via npx) |
| React version | 18.3.1 |
| Vite version | 6.4.3 |
| TypeScript version | 5.7.3 |
| Vitest version | 2.1.9 |
| `pnpm install --dir frontend` | Exit 0, 265 packages |
| `pnpm test -- --run` | 3 passed |
| `pnpm lint` | 0 errors |
| `pnpm build` | dist/index.html created |
| `git check-ignore frontend/dist/index.html` | ignored |

### Commands Executed

```bash
npx pnpm install --dir frontend
npx pnpm --dir frontend test -- --run
npx pnpm --dir frontend lint
npx pnpm --dir frontend build
```

### Deviation

pnpm 未全局安装，使用 `npx pnpm` 替代。

---

## Task 3: MySQL Compose and Environment Doctor

### Verification

| Item | Result |
|------|--------|
| `docker compose config` | Exit 0, valid config |
| `docker compose up -d mysql` | Container started, healthy |
| `docker exec mysql ... phase_0_health` | `status = ok` |
| `doctor.py --offline` | Exit 0, "All offline checks passed" |
| `doctor.py --mysql` (MySQL running) | Exit 2 — mysql-connector-python not installed (network limited) |
| `doctor.py --mysql` (MySQL stopped) | Exit 2 — same reason |
| `doctor.sh --offline` | Exit 0, delegates to venv Python |
| `pytest tests/unit/test_doctor.py -q` | 3 passed in 0.11s |

### Commands Executed

```bash
docker compose config
docker compose up -d mysql
docker compose ps mysql
docker exec research-copilot-mysql mysql -uroot -proot -e "SELECT status FROM research_copilot.phase_0_health;"
.venv/bin/python scripts/doctor.py --offline
.venv/bin/python scripts/doctor.py --mysql
.venv/bin/python -m pytest tests/unit/test_doctor.py -q
```

### Known Limitations

- `mysql-connector-python` 未能安装（PyPI 网络不可达）。doctor `--mysql` 模式当前退出码 2 表示依赖缺失。MySQL 健康表已通过 `docker exec` 直接验证。
- 当网络恢复后，安装 `mysql-connector-python` 即可完成完整的 `--mysql` 验证。

---

## Task 4: CI, Pre-commit, Secret Scanning

### Verification

| Item | Result |
|------|--------|
| CI config created | `.github/workflows/ci.yml` — Python + Frontend jobs |
| pre-commit config created | `.pre-commit-config.yaml` — ruff, detect-secrets |
| `ruff check app tests scripts` | All checks passed |
| `ruff format --check app tests scripts` | All checks passed |
| `pytest tests/ -q` | 6 passed in 0.47s |
| Secret scan (manual regex) | No secrets in tracked files |
| Fake secret detection test | `sk-test-not-a-key` correctly detected |

### Commands Executed

```bash
uv run ruff check app tests scripts
uv run ruff format --check app tests scripts
uv run pytest tests/ -q
git ls-files | xargs grep -lE 'sk-[a-zA-Z0-9]{20,}|api_key...'  # clean
```

### Known Limitations

- `pre-commit install` 和 `detect-secrets` 未安装（PyPI 网络不可达）。`.pre-commit-config.yaml` 和 `.secrets.baseline` 已创建，待网络恢复后执行 `pre-commit install && pre-commit run --all-files`。
