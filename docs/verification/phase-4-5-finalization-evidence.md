# Phase 4.5 Portfolio Finalization Evidence

**Date:** 2026-08-12

**Implementation start baseline:** `main` at
`ce3e2f96420b20994af082997283d7809e2b6055`.

**Final checkpoint:** `3a84c58` (`feat: complete phase 4.5 research showcase`).

Implementation began from a large dirty worktree containing the uncommitted
P4.5-2 through P4.5-6 changes. The authorized local checkpoint commit captured
the accepted implementation and left the worktree clean. No push, tag, merge,
release, or deployment was performed.

## Reliability Closeout

- Model-visible source content is bounded before invocation and the final AI
  answer is selected without concatenating intermediate worker messages.
- The knowledge route has an explicit manifest validation/indexing CLI,
  stable point IDs and document-snapshot replacement that removes stale chunks
  without touching sibling documents.
- Missing, corrupt, locked, or fingerprint-mismatched local knowledge state
  degrades only the knowledge source with a structured limitation.
- The real smoke leak matcher now distinguishes actual token prefixes from
  ordinary words such as `task-` and `mask-`.
- The MySQL adapter forces Connector/Python pure mode, avoiding the observed
  macOS ARM64 C-extension crash while preserving the read-only contract.
- Browser acceptance exposed an uploaded-source link that resolved against the
  Vite origin. A focused RED/GREEN component change now resolves the already
  validated thread-scoped path against `apiBaseUrl` without changing the live
  wire, report, or backend path contract.

## Complete Offline Gates

| Command | Result |
|---|---:|
| `PYTHONPATH=. .venv/bin/pytest -q` | 1133 passed, 15 skipped, 1 existing Starlette/httpx deprecation warning; exit 0 |
| `.venv/bin/ruff check .` | passed; exit 0 |
| `.venv/bin/ruff format --check app tests scripts` | 148 files already formatted; exit 0 |
| `git diff --check` | passed; exit 0 |
| `pnpm --dir frontend exec vitest run` | 120 passed; exit 0 |
| `pnpm --dir frontend lint` | exit 0 |
| `pnpm --dir frontend build` | 31 modules transformed; exit 0 |

The first format check identified six files. Ruff formatted exactly those six,
and the affected backend regression then passed `62` tests before the final
format check above.

After the browser-found upload-link defect, the focused test first failed with
the relative `5173` href, then passed after the minimal change. The complete
frontend gates were rerun with the results shown above.

## Deterministic Offline Reproduction

The fixed four-source Showcase fixture was executed twice in separate temporary
directories. The complete canonical live-citation JSON and artifact-name tuple
matched exactly:

```text
deterministic=pass sources=4 evidence=4 artifacts=3
```

The first exploratory comparison used an upload fixture with the wrong thread
and correctly produced only three sources; it was discarded and is not counted
as deterministic evidence.

## Local FastEmbed And Knowledge Boundary

The separately authorized adapter smoke ran:

```text
PHASE45_FASTEMBED_SMOKE=1 PYTHONPATH=. .venv/bin/pytest -q \
  tests/integration/phase4_5/test_local_knowledge_smoke.py

1 passed in 19.43s
```

It used a pytest temporary Qdrant Local path and the configured FastEmbed cache.
The cache currently occupies about `240M` under `.cache/fastembed` and is
ignored by Git. The configured `.data/knowledge-index` is absent and its ignore
rule is verified. No formal knowledge corpus was built, indexed, or evaluated.

## Authorized Real Showcase Smoke

The user explicitly authorized the bounded real Showcase command. Capability
state was recorded without credential values:

| Capability | Result |
|---|---|
| Model | configured DeepSeek endpoint; exercised |
| Web | Tavily configured; exercised |
| MySQL | configured read-only local source; exercised |
| Knowledge | formal local index absent; structured unavailable behavior |
| Uploaded file | non-sensitive thread-scoped fixture; exercised |

The first run reached `task_completed` and generated valid artifacts, but the
test failed because the leak matcher treated substrings in ordinary words as an
API token. Direct byte comparison against the configured secrets found no
secret in the artifacts. The matcher received a RED/GREEN regression.

The second run terminated in `mysql.connector.connection_cext._open_connection`
with a Python segmentation fault. The adapter received a failing test and the
minimal `use_pure=True` correction; its focused suite passed `7` tests.

The explicitly authorized corrected run then completed:

```text
PHASE45_REAL_SHOWCASE_SMOKE=1 PYTHONPATH=. .venv/bin/pytest -q \
  tests/integration/phase4_5/test_real_showcase_smoke.py

2 passed in 625.38s (0:10:25)
exit 0
```

This proves the bounded real LLM/Tavily/MySQL/upload execution, one terminal
event, live citation schema `2.0.0`, source/evidence integrity, and redacted
JSON, Markdown, and PDF artifacts. It does not establish Provider quality,
knowledge retrieval accuracy, production readiness, or formal corpus quality.

## Browser Acceptance

A deterministic ASGI fixture outside the repository exercised the React
Showcase without credentials, real Providers, network sources, or the formal
knowledge index.

- At `1440x900`, task upload/submission reached Success and displayed 2 claims,
  4 evidence records, all four source kinds, the knowledge limitation, three
  artifact events, one terminal event, report preview, and Markdown/PDF links.
- At `375x812`, the same flow rendered in one column in answer, claims,
  coverage, limitations, sources, reports, and timeline order. The first claim
  displayed all four linked evidence records.
- Both viewports had `scrollWidth == clientWidth`, no inspected control or
  section exceeded the viewport, and no stuck loading state appeared.
- Web and report links were safe; Markdown and PDF requests returned `200` in
  the API log.
- Screenshots were written outside Git at `/private/tmp/phase45-desktop.png`
  and `/private/tmp/phase45-mobile.png`.

The smoke found that the uploaded-source link was relative to the Vite origin,
which reopened the app instead of the file. The component regression now
requires the API-origin absolute URL and the full frontend gate is green.

After explicit browser re-authorization, the deterministic upload/task flow was
run again. Clicking `Open uploaded source` produced a browser download event
whose href and resolved URL were both the API-origin thread-scoped route. The
download contained `59` bytes and matched the uploaded fixture byte-for-byte;
the API log recorded the exact `/api/threads/<thread>/uploads/showcase-notes.txt`
request with status `200`.

All temporary API and Vite processes were stopped after the run.

## Leak And Repository Scans

- The current runtime/config/canonical-route RAGFlow scan returned zero hits.
- Remaining repository RAGFlow mentions are confined to the migration design,
  finalization instructions that name the removal scan, and explicitly
  historical ADRs, Phase 0-2 plans/runbooks, old design records, examples, and
  verification evidence. They preserve historical facts and are excluded from
  canonical execution context.
- The current route contains no token-shaped `sk-` or `tvly-` values. Remaining
  repository matches are synthetic negative-test fixtures or historical
  examples, not credentials.
- Runtime absolute-path matches are comments describing redaction rules;
  executable test matches are deliberate traversal/path-redaction inputs.
- The only current raw-response marker is a frontend negative test proving such
  a field is rejected.
- `.cache/fastembed`, `.data/knowledge-index`, `frontend/dist`, and runtime
  `output/*` paths are ignored. None appears as an untracked deliverable.
- `.env` is not tracked and was never printed or copied into evidence.

## Acceptance Decision

P4.5-6 is **accepted at checkpoint `3a84c58`**. The full offline/static gates,
deterministic replay, authorized real Showcase smoke, desktop/mobile flow, safe
source links, and artifact downloads passed. The local checkpoint exists and
the worktree was clean after its creation. No push, tag, merge, release, or
deployment was performed.
