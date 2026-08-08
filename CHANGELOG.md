# Changelog

All notable changes to this project are documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

No unreleased implementation changes.

### Documentation

- Freeze the accepted Phase 4 boundary and define Phase 4.5 as the canonical
  live-source research showcase stage before Phase 5 orchestration work.

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
