# Phase 1 Release Closure Evidence

## Scope

This release-closure pass makes the Phase 1 environment reproducible, aligns CI
with the local gate, removes host-state coupling from the MySQL failure test,
and prepares the accepted Phase 1 release for the Phase 2 planning gate.

## Remediations

- `pre-commit` and `detect-secrets` are declared in the optional `dev` extra and
  locked in `uv.lock`.
- `test_doctor_mysql_unavailable_exits_nonzero` explicitly uses local port `1`
  to verify connection refusal, so it passes whether the project MySQL service
  is running or stopped.
- The root frontend test script and README use `pnpm --dir frontend exec vitest run`,
  which exits after one test run rather than starting watch mode.
- CI now checks examples with Ruff, formatting, pre-commit hooks, Compose
  configuration and the offline environment doctor.
- `detect-secrets scan --baseline` is not a final gate because it rewrites the
  baseline timestamp. The non-mutating pre-commit `detect-secrets` hook is the
  release security check.

## Fresh Verification

| Gate | Command | Exit | Result |
|---|---|---:|---|
| Frozen Python environment | `uv sync --extra dev --frozen` | 0 | 102 packages checked; hooks installed from project metadata |
| Python tests | `.venv/bin/python -m pytest tests/ -q` | 0 | 83 passed, 2 real-model tests skipped without `MODEL_API_KEY` |
| Ruff lint | `.venv/bin/ruff check app examples tests scripts` | 0 | passed |
| Ruff format | `.venv/bin/ruff format --check app examples tests scripts` | 0 | 33 files already formatted |
| Hooks and secrets | `.venv/bin/pre-commit run --all-files` | 0 | ruff, ruff-format and detect-secrets passed |
| Frontend test | `pnpm --dir frontend exec vitest run` | 0 | 3 passed |
| Frontend lint | `pnpm --dir frontend lint` | 0 | passed |
| Frontend build | `pnpm --dir frontend build` | 0 | TypeScript check and Vite build passed |
| Compose | `docker compose config` | 0 | MySQL maps host 3307 to container 3306 |
| Offline doctor | `.venv/bin/python scripts/doctor.py --offline` | 0 | Python 3.12.7 accepted |
| MySQL doctor | `.venv/bin/python scripts/doctor.py --mysql` | 0 | `phase_0_health` contains `ok` |
| Offline agent examples | runner: interrupt/resume, backend/store/memory, middleware/skills | 0 | all completed without a model key |
| Diff whitespace | `git diff --check` | 0 | passed |

## Phase 2 Boundary

Phase 2 is `ready_to_start`, not in progress. The release contains no Tutorial
Parity implementation: no business agent, Tavily integration, RAGFlow client,
WebSocket workflow, report delivery, file upload or business frontend has been
introduced. The next required artifact is the precise Phase 2 implementation
plan; code execution still requires explicit user authorization.

## Known Limitations

- Real-model smoke coverage remains intentionally skipped until `MODEL_API_KEY`
  is configured.
- The MySQL release check uses the dedicated host port 3307 and leaves no
  dependency on another local project using port 3306.
