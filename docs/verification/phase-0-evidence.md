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
