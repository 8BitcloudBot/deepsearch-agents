# Changelog

All notable changes to this project are documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- MySQL now binds to host port 3307 by default while retaining container port 3306, allowing coexistence with another local MySQL project on host port 3306.
- Compose no longer uses a fixed container name; `MYSQL_HOST_PORT` and `MYSQL_PORT` can be overridden for custom environments.

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

### Fixed

- Phase 0-1: Acceptance Blocker Remediation
  - Ruff format now passes on all files
  - mysql-connector-python installed; doctor --mysql exits 0 when MySQL running, non-zero when stopped
  - pre-commit hooks (ruff, ruff-format, detect-secrets) execute and pass
  - detect-secrets baseline generated and verified with fake secret detection
  - Frontend verified with Node 22.14.0 per .nvmrc
  - docs/superpowers design and plan documents committed
