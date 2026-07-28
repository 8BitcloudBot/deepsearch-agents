# Changelog

All notable changes to this project are documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Phase 0: Foundation and Execution Discipline (awaiting acceptance)
  - Git repository initialization and governance files
  - Python 3.12 health contract: `GET /health` returns `{"status":"ok","service":"research-copilot-api","phase":"0"}`
  - React/Vite frontend shell with test/lint/build pipeline
  - Docker Compose MySQL 8.0 with idempotent `phase_0_health` table
  - Environment doctor (`doctor.py --offline`, `doctor.py --mysql`)
  - GitHub Actions CI: Python + Frontend jobs
  - pre-commit config: ruff + detect-secrets
  - ADR 0001: Phase 0 Boundaries
