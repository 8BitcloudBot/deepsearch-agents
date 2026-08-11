# P4.5-5 React Showcase Polish Evidence

**Date:** 2026-08-10

**Branch:** `main`

**Baseline:** `ce3e2f9`; P4.5-2 through P4.5-5 remain uncommitted in the
current worktree.

## Scope

P4.5-5 adds the thread-scoped uploaded-source route, exact live-citation
frontend types and fail-closed parsing, profile-aware citation/artifact
routing, the claim-first `ShowcaseResults` surface, and responsive desktop and
mobile presentation. Existing tutorial, agent-research, `/api/citations`,
WebSocket, `/api/files`, `/api/download`, report, and Phase 4 citation contracts
remain in place.

No real model, Provider, network source, credential, production data, commit,
push, tag, release, or deployment was used.

## Automated Gates

Backend focused contract gate:

```text
PYTHONPATH=. UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run pytest \
  tests/integration/phase4_5/test_showcase_delivery_api.py \
  tests/integration/phase2/test_api_contract.py -q

67 passed, 1 warning in 0.55s
```

The warning is the existing Starlette `httpx` TestClient deprecation notice.

Frontend package gate:

```text
pnpm --dir frontend exec vitest run

Test Files  2 passed (2)
Tests       120 passed (120)
```

Static and build gates:

```text
pnpm --dir frontend lint
eslint src --ext .ts,.tsx

pnpm --dir frontend build
tsc -b && vite build
31 modules transformed; production build completed

UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run ruff check \
  app/api tests/integration/phase4_5
All checks passed!

UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run ruff format --check \
  app/api tests/integration/phase4_5
9 files already formatted

git diff --check
passed with no output
```

## Deterministic Browser Smoke

The local API used `APP_PROFILE=showcase`, explicit source capability flags,
and no model key, so the runtime followed the fail-closed model-unavailable
path without contacting a model or source Provider. A local canonical Markdown
file was uploaded to the current thread.

- The task produced one honest zero-evidence claim, four stable source coverage
  rows, a model-unavailable limitation, Markdown/PDF controls, and the complete
  activity timeline.
- The first claim disclosure was open by default and native close/reopen
  interaction worked.
- Web/upload link rules and absent MySQL/knowledge links are covered by the typed
  component/parser tests; the zero-source smoke exposed no unsafe link.
- At 1440 CSS pixels the result grid resolved to two columns and the activity
  timeline followed the result.
- At 375 CSS pixels the grid resolved to one column in claim, inspection,
  limitation, source, report, then activity order.
- At both viewports `scrollWidth` equaled `clientWidth`; there was no horizontal
  overflow or overlap.
- Keyboard focus used a visible 2 px outline. Browser console warning/error
  logs were empty.

Local API and frontend processes were stopped after the smoke.

## Acceptance

P4.5-5 is complete in the current worktree. P4.5-6 is the next package and
still requires explicit authorization for real Provider/source execution.
