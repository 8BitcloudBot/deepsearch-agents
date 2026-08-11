# Knowledge Retrieval Migration Evidence

**Date:** 2026-08-11

**Baseline:** `main` at `ce3e2f9`; all changes remain uncommitted in the
working tree. No commit, push, tag, merge, release, deployment, network call,
real provider request, production data, or private knowledge document was used.

## RED

- The first frontend live-citation run failed 21 tests because implementation
  correctly required live schema `2.0.0` while stale test fixtures still used
  `1.0.0`. Fixtures were corrected; the old schema remains covered as a
  rejection case.
- The first fingerprint boundary tests accepted a payload with a mismatched
  embedding fingerprint and did not distinguish embedding and chunking
  fingerprint changes. The adapter now rejects both mismatches and requires
  the embedding fingerprint in every stored payload.
- The migration boundary tests cover missing collections, invalid metadata,
  path traversal, fingerprint mismatch, no evidence, and structured
  knowledge-unavailable behavior.

## GREEN

- Added vendor-neutral `KnowledgeChunk`, `KnowledgeRetriever`,
  `KnowledgeIndexer`, `KnowledgeIndexSpec`, `EmbeddingAdapter`, stable point
  IDs, and index/embedding fingerprints.
- Added Qdrant Local path-mode indexing/retrieval and lazy FastEmbed plus a
  deterministic fake embedder for offline tests. The physical collection name
  includes the index fingerprint; a manifest prevents silent mixed indexes.
  The supported offline default model is
  `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (FastEmbed
  `0.8.0`, 384 dimensions); adapter construction remains lazy.
- Replaced the business source kind and locator with `knowledge` and
  `KnowledgeChunkLocator`; the showcase tool is retrieval-only
  `showcase_search_knowledge`.
- Switched runtime, API/WebSocket, report, frontend parser/types/UI, fixtures,
  settings, dependency lock, `.env.example`, and `.gitignore` to the generic
  knowledge route. The existing `/api/citations` Phase 4 contract remains
  unchanged; live citations use schema `2.0.0`.
- Removed the legacy provider module, SDK dependency, runtime branches,
  credentials, and provider-specific tests. Historical documents are explicitly
  marked and excluded from the canonical execution context.

## Verification

| Gate | Result |
|---|---:|
| `PYTHONPATH=. .venv/bin/pytest -q tests/unit/knowledge tests/unit/phase4_5 tests/integration/phase4_5 --ignore=tests/integration/phase4_5/test_local_knowledge_smoke.py` | 170 passed |
| Phase 4 citation regression (`tests/integration/phase4 tests/unit/phase4_5/test_showcase_contracts.py`) | 76 passed, 1 skipped |
| `PYTHONPATH=. .venv/bin/pytest -q` | 1101 passed, 14 skipped |
| `pnpm vitest run` | 120 passed |
| `pnpm lint` | exit 0 |
| `pnpm build` | exit 0 |
| `.venv/bin/ruff check .` | exit 0 |
| `.venv/bin/ruff format --check app tests` | 140 files formatted |
| `git diff --check` | exit 0 |
| `PHASE45_FASTEMBED_SMOKE=1 PYTHONPATH=. .venv/bin/pytest -q tests/integration/phase4_5/test_local_knowledge_smoke.py` | 1 passed, 19.43s |

All default tests use deterministic fakes/fixtures and do not load or download
an embedding model, contact a provider, or write the configured real index.

## Smoke And Data Boundary

The authorized smoke used the configured FastEmbed cache directory
(`.cache/fastembed`) for the downloaded model and a pytest temporary directory
for the Qdrant Local index. The configured production index directory
(`.data/knowledge-index`) remains absent. No formal knowledge corpus has been
built, indexed, or evaluated in this migration.

## Remaining Legacy Mentions

The final repository search leaves legacy provider names only in the migration
design and explicitly marked historical ADRs, plans, phase records, runbook,
and verification/evidence files. They preserve the fact that the original
tutorial or migration decision used that provider; none is in runtime code,
configuration, current Phase 4.5 guidance, frontend code, or the canonical
documentation reading order.

## Risks

- The local adapter smoke passed, but it does not measure formal corpus quality
  or retrieval accuracy.
- Formal knowledge data and ingestion/chunking operations are intentionally
  out of scope; only non-sensitive deterministic fixtures are indexed in tests.
- The `KnowledgeRetriever`/`EmbeddingAdapter` seam is ready for a future
  Qdrant Server + TEI adapter, but Server and TEI are not implemented here.
