# Formal Showcase Knowledge Evidence

**Date:** 2026-08-13

**Baseline:** local `main` at `2d07e3d`, one existing documentation commit
ahead of `origin/main`, plus preserved uncommitted Phase 9 work.

**Scope:** K1-K6 formal local knowledge package. K6 used one explicitly
authorized real LLM Showcase smoke with only local Qdrant knowledge and a
fixed uploaded fixture enabled. Tavily, host MySQL, production data, push,
tag, Release, deployment, and Phase 5-8 work were not used.

## Source And Build Boundary

Six official sources were selected after reviewing nine candidates. The
structured comparison in `data/knowledge/showcase-v1/candidates.json` records
each candidate's official URL, publisher, frozen version, retrieval date,
license, estimated normalized characters and chunks, selection value,
intended questions, recommendation, and decision reason. The repository
contains only this comparison, source metadata, frozen commits, licenses,
content hashes, the explicit build catalog, and the fixed question set.
Third-party document bodies remain under the ignored
`.data/knowledge-corpus/` directory.

The normalized corpus contains:

| Measure | Result |
|---|---:|
| Documents | 6 |
| Semantic chunks | 140 |
| Normalized characters | 92,101 |
| Chunk characters | min 33; median 538; max 1,797 |
| DeepAgents / LangGraph / Qdrant / FastEmbed chunks | 10 / 12 / 15 / 12 |
| OWASP / Ragas chunks | 34 / 57 |

The corpus is about 264 KiB including the local manifest, below the earlier
1-3 MB planning estimate. Repeating text to reach a byte target would weaken
retrieval quality and conflict with the 80-180 semantic chunk target, so the
package preserves 140 high-density chunks and records the deviation.

## Validation And Indexing

Validate-only output:

```text
collection=deepsearch-showcase-v1 documents=6 chunks=140
fingerprint=5a2604519fc10a9c722d77aae3f20d46f4a25628f13f3168b1457afd5118ae0c
indexed=0 skipped=0
```

Before and after validate-only, the index directory remained absent and the
FastEmbed cache size/mtime fingerprint was unchanged. The command printed no
source body or absolute path.

The first formal index build reported `indexed=140 skipped=0`; an immediate
second build reported `indexed=0 skipped=140`. The path-backed index is about
780 KiB. The local FastEmbed cache is about 240 MiB and was already populated
by an explicitly authorized earlier adapter smoke.

| Artifact | SHA-256 |
|---|---|
| ignored corpus manifest | `17ee8aef1206212706991866015d58ee0297fe4d41dc4bc18f669349e4f6685c` |
| ignored index manifest | `454c995404c58dc16e2e96f432740d28ea260e96fd377c0d88f8e048e47a8717` |
| index fingerprint | `5a2604519fc10a9c722d77aae3f20d46f4a25628f13f3168b1457afd5118ae0c` |

FastEmbed emitted its known warning that this model now uses mean pooling
rather than the previous CLS behavior. The dependency lock and model
descriptor are part of this result; this record does not claim reproducibility
across unfrozen FastEmbed versions.

## Fixed Retrieval Set

The 13-question run completed with:

```text
questions=13 passed=13 failed=0 no_evidence=1
```

The ignored evaluation report SHA-256 is
`9431bb49ee3e62e05c7cf9fb625a954718642cfc3b7650f2626a169a3110ccb9`.
The formal index manifest hash and disk size were unchanged before and after
evaluation.

This is a deterministic acceptance set. `13 passed` means the declared Top-K
document/chunk/section and no-evidence expectations were met at score threshold
`0.40`; it is not a retrieval accuracy, answer correctness, or quality rate.

## Showcase Contract Closure

The explicit local integration smoke was run with:

```bash
SHOWCASE_FORMAL_KNOWLEDGE_SMOKE=1 PYTHONPATH=. .venv/bin/pytest \
  tests/integration/phase4_5/test_formal_knowledge_showcase.py -q
```

Result: `1 passed`, plus the FastEmbed pooling warning described above.

The smoke proves the formal evidence passes through local Qdrant + FastEmbed,
`showcase_search_knowledge`, the model-visible untrusted-data boundary,
bounded/redacted source normalization, `LiveSourceCollector`, citation schema
`2.0.0`, a shared `collection:document:chunk` locator, the official document
title, Markdown, and PDF. With the opt-in flag absent, the test skips before
opening the index or loading FastEmbed.

The explicit Phase 9 demo integration smoke was also run with:

```bash
SHOWCASE_FORMAL_KNOWLEDGE_SMOKE=1 PYTHONPATH=. .venv/bin/pytest -q \
  tests/integration/phase9/test_portfolio_demo_app.py::test_formal_knowledge_scenario_opens_the_real_local_index
```

Result: `1 passed`, plus the same FastEmbed pooling warning. This smoke uses
the production CLI index assembler and actual formal index through the
upload, task, live-citation, Markdown, and PDF boundaries. The runnable
`formal-knowledge` scenario keeps Web, MySQL, and upload repository-safe and
deterministic, replaces the LLM with local deterministic text, and retrieves
only the knowledge evidence from Qdrant Local + FastEmbed.

The nearest non-model regression surface passed with `53 passed`; stale-chunk,
bounded-output, redaction, and no-evidence checks passed with `4 passed`; the
focused React result suite passed with `37 passed` after adding the formal
title and full locator fixture.

## Browser Acceptance Boundary

Desktop `1440x900` and mobile `375x812` browser acceptance was attempted
against the runnable `formal-knowledge` scenario. The sandbox rejected both
the loopback ASGI bind on `127.0.0.1:8000` and Vite bind on
`127.0.0.1:5173` with `EPERM`. A controlled escalation of those same standard
commands was then rejected by the environment safety reviewer, which
explicitly prohibited workaround, indirect execution, or switching browser
surfaces.

No desktop/mobile screenshot or overflow measurement is therefore claimed for
the formal knowledge fixture. Existing Phase 9 screenshots continue to prove
the deterministic portfolio UI only. Component tests prove the official title,
full locator, and Markdown/PDF controls render; the local integration smoke
proves the backend artifact chain; neither is mislabeled as a browser E2E.

The user explicitly waived formal-knowledge browser screenshots and requested
functional-chain review instead. K5 is therefore accepted on the actual-index
backend smoke, citation/report contracts, and the focused React contract suite;
no desktop/mobile screenshot or overflow claim is made for this fixture. The
actual-index ASGI smoke proves that the browser has a runnable backend scenario.

## Final Offline Gates

The final worktree produced these fresh results:

| Gate | Result |
|---|---:|
| `PYTHONPATH=. .venv/bin/pytest -q` | `1163 passed, 17 skipped`; one existing Starlette/httpx deprecation warning |
| `pnpm --dir frontend exec vitest run` | `120 passed` |
| `pnpm --dir frontend lint` | passed |
| `pnpm --dir frontend build` | 31 modules transformed; production build passed |
| `.venv/bin/ruff check .` | passed |
| `.venv/bin/ruff format --check app tests scripts examples` | 178 files already formatted |
| `.venv/bin/pre-commit run --all-files` | Ruff, Ruff format, and Detect Secrets passed |
| `.venv/bin/python scripts/doctor.py --offline` | Python 3.12.7; all offline checks passed |
| `docker compose config --quiet` | passed |
| `git diff --check` | passed |
| local Markdown target check | `markdown-links=pass files=80` |

The repository's exact `uv run` forms could not initialize the sandboxed
`/Users/wxhu/.cache/uv` path. A controlled escalation was rejected by the
environment safety reviewer, so the same locked project environment was
exercised through the existing `.venv` executables shown above. This is an
execution-environment limitation, not a claim that the literal `uv run`
commands completed in this session.

A fresh manifest rebuild from the explicit local catalog matched the formal
manifest byte-for-byte and retained SHA-256
`17ee8aef1206212706991866015d58ee0297fe4d41dc4bc18f669349e4f6685c`.
The frozen source checkouts were copied into the catalog's declared relative
layout under a temporary verification directory; no repository source body was
created. Validate-only from that directory used a confirmed-absent relative
index path, reported 6 documents, 140 chunks, the expected fingerprint,
`indexed=0 skipped=0`, and did not create that path. A final real-index rerun reported
`indexed=0 skipped=140` and retained the same index-manifest hash.

Git ignore checks confirmed that third-party bodies, the built corpus
manifest, Qdrant index, evaluation result, and FastEmbed cache are excluded.
Scope/leak scans found no public absolute path or RAGFlow route; Phase 5-8,
production readiness, and retrieval accuracy appear only as explicit
non-goals or forbidden extrapolations. The `/Users/` strings retained in the
React test file are negative fixtures that verify unsafe payload rejection.

## K6 Real Showcase Smoke

The user then explicitly authorized one real Showcase smoke using the fixed
request/upload fixture and the `.env` model configuration. The command loaded
`.env` without printing its values and overrode the enabled capability boundary
to `knowledge,uploaded-file` with `KNOWLEDGE_PROVIDER=qdrant-local`; Tavily and
MySQL were not constructed.

```bash
APP_PROFILE=showcase SHOWCASE_ENABLED=1 SHOWCASE_SOURCES=knowledge,uploaded-file \
KNOWLEDGE_PROVIDER=qdrant-local PHASE45_REAL_SHOWCASE_SMOKE=1 PYTHONPATH=. \
  .venv/bin/pytest -q \
  tests/integration/phase4_5/test_real_showcase_smoke.py
```

Result: `2 passed` in `120.44s` with the known FastEmbed mean-pooling warning.
The temporary citation document contained a non-empty answer, 28 sources and
28 evidence items, and both enabled source kinds: one `uploaded-file` span and
27 `knowledge` chunks. Knowledge locators retained the canonical
`deepsearch-showcase-v1:document:chunk` shape, and the test's artifact leak
scan passed for citation JSON, Markdown, and PDF. Web and MySQL were recorded
as intentionally `not-enabled` limitations.

The model made repeated tool attempts, so the redacted document also records
`knowledge-unavailable`, `source-failed`, and `no-evidence` limitations from
unsuccessful attempts. These are honest runtime observations, not evidence of
retrieval quality or model quality; the passing contract proves successful
artifact and provenance handling for the sources that were captured.

## Acceptance Decision

K1-K5 are accepted under the functional-chain boundary above. K6 is
accepted for the single authorized `knowledge,uploaded-file` run with the
recorded degraded-attempt limitations. Phase 9 acceptance is complete. The
verification run itself did not perform push, tag, Release, or deployment;
`v1.0-portfolio` publication is a separate release action, and deployment is
outside its scope.
