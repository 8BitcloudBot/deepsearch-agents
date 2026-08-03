# Changelog

All notable changes to this project are documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Phase 2 — Tutorial Parity (Tasks 0-7): `tutorial` profile implementing the tutorial baseline (chapters 8-14).
- Three independently selectable providers behind an immutable `ProviderBundle`: web (`mock|tavily`), catalog (`mock|mysql`), knowledge (`mock|ragflow`); real adapters are lazy and never constructed at import time; provenance travels only in explicit mode fields.
- Deterministic offline runtime (`MockTutorialRuntime`) and real DeepAgents runtime (`DeepAgentsTutorialRuntime`) behind one `TutorialRuntime` protocol; mock mode requires no model key or network.
- Concrete in-memory event bus: per-thread monotonic `sequence`, bounded 256-event live-only subscriptions, overflow signal (WebSocket close 1013), strict JSON-only `data` validation; no history, replay, or persistence (Phase 7).
- FastAPI/WebSocket closure: `POST /api/task`, `POST /api/task/{thread_id}/cancel`, `POST /api/upload`, `GET /api/files`, `GET /api/download`, `WS /ws/{thread_id}`; in-memory `TaskRegistry` owns `task_started` and exactly one terminal event; heartbeat `{"type":"pong"}` is separate from `TutorialEvent`; task redaction, cancellation-before-entry, and download containment.
- Per-thread workspace isolation (`updated/session_<thread_id>/`, `output/session_<thread_id>/`), safe upload parsing (.txt/.md/.pdf/.docx/.xlsx, 10 MiB limit, traversal/macro/ZIP-bomb defenses), Markdown and PDF report generation with relative artifact paths.
- Controlled read-only MySQL: sqlglot AST validation plus a SELECT-only `tutorial_reader` account, `MAX_EXECUTION_TIME(5000)` and wrapped `LIMIT` enforcement, idempotent `docker/mysql/init/010_tutorial.sql` bootstrap for fresh and preserved volumes.
- React 18 Tutorial Workbench (Vite/TypeScript/Vitest/Playwright): WebSocket event feed, 25s ping heartbeat, upload, run/cancel, Markdown preview, artifact downloads; Playwright Chromium at 1440x900 and 390x844 with deterministic route fixtures.
- CI: Python job runs all offline Phase 2 tests without services/network; frontend job on Node 22 installs Playwright Chromium then runs Vitest, lint, build, and Playwright browser tests.
- Tutorial runbook `docs/phase-2-tutorial.md`: mock quick start, mixed-provider configuration, MySQL bootstrap for fresh and preserved volumes, external RAGFlow/Tavily/real-model opt-ins, API/WebSocket examples, heartbeat vs event shapes, live-only semantics, cancellation, limitations, and the chapter 8-14 matrix.

### Known Limitations

- Tasks and events are in-memory only: no persistence, reconnect replay, or recovery (Phase 7); a WebSocket disconnect does not cancel the task.
- Real-service smokes (Tavily, RAGFlow, real model) are skipped unless explicitly opted in with credentials; mock success is never reported as real-service success.
- The local Node 22.23.2 / pnpm 11.9.0 frontend compatibility gate has passed (Homebrew `node@22`: offline frozen install, Vitest 22 passed, lint, build, Playwright 2 passed + 2 intentional cross-project skips); the actual Ubuntu CI job using Node 22 with pnpm 10 has not run and remains pending before acceptance.
- RAGFlow is not part of this repository's Compose setup and must be deployed externally.
- `v0.1-tutorial-parity` has not been created; Phase 3 has not started.

## [v0.0-deepagents-examples] - 2026-07-28

### Added

- Seven independently runnable DeepAgents/LangGraph examples: invoke, streaming, dictionary and runnable subagents, interrupt/resume, backend/store/memory, middleware and skills.
- Offline behavioral tests for interrupt/resume, FilesystemBackend, InMemoryStore, MemoryMiddleware, middleware observability and SkillsMiddleware lifecycle loading.
- ADR 0002 documenting the tested DeepAgents 0.6.12 API surface and Phase 2 reuse boundary.

### Fixed

- Skills loading now uses public `SkillsMiddleware.before_agent()` with YAML frontmatter validation instead of directory scanning.
- Phase 1 evidence records RED/GREEN behavior and final verification commands with their real commit history.
- The `dev` extra now declares `pre-commit` and `detect-secrets`, so a frozen environment sync reproduces the local verification toolchain.
- The MySQL-unavailable doctor test uses an explicit refused port instead of assuming a local MySQL service is stopped.
- Root frontend test commands now invoke Vitest in one-shot mode; CI also checks examples, formatting, hooks, Compose configuration and the offline doctor.

### Known Limitations

- Real-model smoke tests require `MODEL_API_KEY` and remain skipped when it is not configured.
- DeepAgents 0.6.12 warns but does not reject a skill whose frontmatter name differs from its directory name.

## [v0.0-foundation] - 2026-07-28

### Added

- Git repository initialization and governance files.
- Python 3.12 health contract: `GET /health` returns `{"status":"ok","service":"research-copilot-api","phase":"0"}`.
- React/Vite frontend shell with test, lint and build pipeline.
- Docker Compose MySQL 8.0 with idempotent `phase_0_health` table.
- Environment doctor (`doctor.py --offline`, `doctor.py --mysql`).
- GitHub Actions CI, pre-commit and detect-secrets baseline.

### Changed

- MySQL now binds to host port 3307 by default while retaining container port 3306, allowing coexistence with another local MySQL project on host port 3306.
- Compose no longer uses a fixed container name; `MYSQL_HOST_PORT` and `MYSQL_PORT` can be overridden for custom environments.

### Fixed

- Phase 0-1: acceptance blocker remediation for Ruff formatting, MySQL doctor, pre-commit and secret scanning.
