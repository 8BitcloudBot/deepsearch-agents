# Agent Engineering Research Copilot Phase 0 Implementation Plan

> **Historical plan:** Phase 0 is accepted. Current boundaries live in
> [`docs/phases/phase-0-foundation.md`](../../phases/phase-0-foundation.md).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax. Stop after Phase 0 acceptance; do not start Phase 1 without explicit user approval.

**Goal:** 建立可重复安装、测试、构建和验收的项目基础设施，为教程基线提供稳定边界。

**Architecture:** 本阶段只创建运行骨架，不实现 Agent 业务能力。Python/FastAPI 提供 `/health`，React/Vite 提供最小页面，MySQL 由 Docker Compose 提供本地依赖；模型、Tavily、RAGFlow 只保留 mock 约束，不在 Phase 0 调用。

**Tech Stack:** Python 3.12、uv、FastAPI、pytest、Ruff、React、Vite、TypeScript、pnpm、Docker Compose、MySQL 8.0、GitHub Actions、pre-commit、detect-secrets。

## Global Constraints

- 只允许修改本计划列出的文件；不得创建 DeepAgents、Tavily/RAGFlow 实调用、教程数据、报告生成或复杂页面。
- 所有命令在 `/Users/wxhu/Documents/reasonix/deepsearch-agents` 执行，真实输出摘要写入 `docs/verification/phase-0-evidence.md`。
- Python 固定 `3.12`；Node 由 `.nvmrc` 固定；包管理器固定 `uv` 和 `pnpm`。
- 离线测试不得需要模型 key、外部服务或运行中的 MySQL。
- 不提交 `.env`、密钥、数据库 volume、运行产物、个人路径和生成报告。
- 每个任务采用 TDD，并创建一个小而完整的 Conventional Commit；禁止 `git add .`。
- 每个任务开始先更新 `docs/phase-status.md`，结束同步验收证据、CHANGELOG 和状态。

## Initial File Map

```text
.gitignore .gitattributes .editorconfig .python-version .nvmrc .env.example
pyproject.toml uv.lock package.json pnpm-lock.yaml
frontend/package.json frontend/index.html frontend/tsconfig.json frontend/vite.config.ts
frontend/vitest.config.ts frontend/src/main.tsx frontend/src/App.tsx frontend/src/app.css frontend/src/App.test.tsx
app/__init__.py app/main.py tests/unit/test_health.py tests/unit/test_doctor.py
docker-compose.yml docker/mysql/init/001_health.sql scripts/doctor.py scripts/doctor.sh
.github/workflows/ci.yml .pre-commit-config.yaml
docs/phase-status.md docs/verification/phase-0-evidence.md docs/adr/0001-phase-0-boundaries.md
CHANGELOG.md README.md output/.gitkeep updated/.gitkeep
```

超出清单必须记录为阻塞并请求决策。

## Task 0: Git and Documentation Contract

**Files:** create `.gitignore`, `.gitattributes`, `.editorconfig`, `.python-version`, `.nvmrc`, `.env.example`, `docs/phase-status.md`, `docs/verification/phase-0-evidence.md`, `docs/adr/0001-phase-0-boundaries.md`, `CHANGELOG.md`, `README.md`.

**Interfaces:** repository root, default branch `main`, status/evidence/ADR paths consumed by later tasks.

- [ ] Verify `pwd` equals the repository path and preserve an existing `.git`.
- [ ] If absent, run `git init -b main` and `git config core.autocrlf input`; never reinitialize an existing repository.
- [ ] Write ignore rules for `.env`, Python/Node caches, `dist`, `coverage`, `output/*` except `output/.gitkeep`, `updated/*` except `updated/.gitkeep`, MySQL volumes and IDE files. `.env.example` contains placeholders only: `APP_ENV=local`, ports, MySQL connection names, empty Tavily/RAGFlow keys.
- [ ] ADR states Phase 0 is infrastructure-only, providers are mocked, MySQL is the only local service, and persistence choice is intentionally undecided. Status starts `in_progress`; README states tutorial and Agent features are not implemented; CHANGELOG starts with `Unreleased`.
- [ ] Run `git check-ignore .env .venv node_modules output/report.md` and `git diff --check`; add explicit paths and commit `chore: initialize project governance`.

## Task 1: Python Health Contract

**Files:** create `pyproject.toml`, `app/__init__.py`, `app/main.py`, `tests/unit/test_health.py`; generate `uv.lock`; update phase docs/README/CHANGELOG.

**Interfaces:** `app.main:create_app() -> FastAPI`; module `app`; `GET /health` returns exactly `{"status":"ok","service":"research-copilot-api","phase":"0"}`.

- [ ] Define project name, Python `>=3.12,<3.13`, runtime FastAPI and uvicorn, dev pytest/httpx/ruff, and test/lint scripts. Do not add LangGraph, DeepAgents, Tavily or RAGFlow.
- [ ] Write `tests/unit/test_health.py` with `TestClient(app).get("/health")`, exact status and JSON assertions. Run `uv run pytest tests/unit/test_health.py -q`; expected initial import failure.
- [ ] Implement `create_app`, `app = create_app()`, and no provider/database globals.
- [ ] Run `uv sync --dev`, `uv run pytest -q`, `uv run ruff check app tests`; start uvicorn, verify with `curl -fsS http://127.0.0.1:8000/health`, then stop it.
- [ ] Record versions, test count, lint and exact response; commit `feat: add phase zero api health contract`.

## Task 2: React/Vite Frontend Skeleton

**Files:** create root/frontend package manifests and lockfile, `frontend/index.html`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/vitest.config.ts`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/app.css`, `frontend/src/App.test.tsx`; update docs.

**Interfaces:** App renders accessible heading `Agent Engineering Research Copilot`, `Phase 0`, and backend URL from `VITE_API_BASE_URL` defaulting to `http://127.0.0.1:8000`; `pnpm test/lint/build` work offline after install.

- [ ] Pin React 18, Vite 6, TypeScript 5, Vitest, Testing Library, ESLint and pnpm. Root scripts delegate to frontend. No component library, WebSocket or business UI.
- [ ] Write render test for heading and Phase 0; run `pnpm --dir frontend test -- --run` and record expected failure before implementation.
- [ ] Implement semantic `main/h1/p`; CSS must be readable, responsive, non-gradient, and free of decorative cards.
- [ ] Run `pnpm install --frozen-lockfile`, frontend test/lint/build; expect `frontend/dist/index.html` and ignored generated files.
- [ ] Record Node/pnpm/output and commit `feat: add phase zero frontend shell`.

## Task 3: MySQL Compose and Environment Doctor

**Files:** create `docker-compose.yml`, `docker/mysql/init/001_health.sql`, `scripts/doctor.py`, `scripts/doctor.sh`, `tests/unit/test_doctor.py`; update `.env.example` and docs.

**Interfaces:** Compose has service `mysql`, MySQL 8.0, port 3306, named volume `mysql_data`, healthcheck; database `research_copilot` has idempotent table `phase_0_health(status PRIMARY KEY)` containing `ok`. `doctor.py --offline` exits 0 without MySQL; `--mysql` checks the table and returns actionable nonzero when unavailable.

- [ ] Write tests for offline success and mocked MySQL-unavailable failure; run them before implementation and record failure.
- [ ] Implement Compose with healthcheck using container-local root credentials (no host secret mount) and idempotent init SQL.
- [ ] Implement argparse CLI, explicit exit codes, no secret printing, and optional MySQL driver import only in `--mysql`. `scripts/doctor.sh` delegates with `exec python3 scripts/doctor.py "$@"`.
- [ ] Run `docker compose config`; `docker compose up -d mysql`; `docker compose ps`; both doctor modes; `docker compose exec -T mysql mysql -uroot -proot -e "SELECT status FROM research_copilot.phase_0_health;"`; `docker compose down`. Then run `python scripts/doctor.py --mysql` while stopped and record its nonzero failure.
- [ ] Commit `chore: add local mysql health dependency`.

## Task 4: CI, Pre-commit, Secret Scanning

**Files:** create `.github/workflows/ci.yml`, `.pre-commit-config.yaml`; update `pyproject.toml`, root package scripts and docs.

**Interfaces:** CI on push/PR runs Python sync/test/lint and frontend frozen install/test/lint/build, never external providers. Pre-commit runs Ruff, formatting, frontend checks where configured, and detect-secrets.

- [ ] Use pinned GitHub Action versions and frozen lockfile commands. Add a detect-secrets baseline only if required and ensure it has no real secret.
- [ ] Run locally: `pre-commit install`; `pre-commit run --all-files`; all Python checks; frontend test/lint/build.
- [ ] Create a temporary untracked fake `sk-test-not-a-key`, confirm scanner reports it, remove it, and record result; do not commit fixture.
- [ ] Commit `ci: enforce phase zero verification`.

## Task 5: Acceptance and Handoff

**Files:** update status/evidence/README/CHANGELOG; create `output/.gitkeep` and `updated/.gitkeep` only if missing.

- [ ] From clean state run `git status --short`, `uv sync --frozen`, `pnpm install --frozen-lockfile`, Python tests/lint, frontend test/lint/build, `docker compose config`, and both doctor modes with MySQL up.
- [ ] Run `rg -n "DeepAgents|Tavily|RAGFlow|WebSocket|report|drug|medicine" app frontend tests docker scripts`; inspect and reject business/provider/tutorial implementation.
- [ ] Evidence must contain timestamp, commit SHA, OS, Python/Node/uv/pnpm/Docker versions, every command/exit code/output summary, known limitations, and stopped-MySQL failure check.
- [ ] Before user acceptance, commit `docs: record phase zero verification` and set status `awaiting_user_acceptance`. Only after explicit acceptance create annotated tag `v0.0-foundation`; do not write or execute Phase 1.

## Phase 0 Acceptance Checklist

- [ ] Git on `main`, explicit commits, clean status.
- [ ] Python 3.12 + `uv.lock`; exact health contract passes.
- [ ] Frontend lockfile; test/lint/build pass.
- [ ] MySQL health table and unavailable-service evidence pass.
- [ ] Offline doctor and secret scan pass without external keys.
- [ ] CI/pre-commit pass; status/evidence/ADR/README/CHANGELOG current.
- [ ] No Phase 1/2/3 code or data.
- [ ] User explicitly accepts evidence before tag and Phase 1 planning.

## DeepSeek Handoff Rules

DeepSeek first returns exact file list and task order. It must not invent files, dependencies, endpoints, tables, UI features or provider integrations. For each task report failing test, minimal implementation, commands/output, changed files, commit SHA and documentation updates. Deviations are blockers in `docs/phase-status.md`; after Task 5 stop and wait for user acceptance.
