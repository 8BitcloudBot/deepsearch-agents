# Phase 3 Verification Evidence

> **P3-7 Integrated Acceptance — 2026-08-08:** Phase 3 (P3-1–P3-7) is accepted.
> All fresh gates below were run on the **current uncommitted worktree** at
> **branch `main`, HEAD `364180d54a4c7b3141147f58b64b8ddd47d1b851`** (the
> accepted Phase 2 release HEAD), i.e. every fresh Phase 3 report records
> **`git_commit=364180d54a4c7b3141147f58b64b8ddd47d1b851`, `git_dirty=true`**.
> This is *not* a clean committed checkpoint: a clean checkpoint commit,
> tag/push/release, and Phase 4 activation all require later explicit user
> authorization and are not performed by this node. Phase 4 remains
> **not started / planned**; its frozen input boundary is recorded below and in
> [`docs/phases/phase-4-trustworthy-citations.md`](../phases/phase-4-trustworthy-citations.md).

**Environment:** macOS darwin/arm64 · Python 3.12.7 (`.venv`, uv-managed) ·
pytest 8.4.2 · ruff 0.16.0 · pnpm/node frontend (vite 6.4.3).

**Date:** 2026-08-08 · **Branch:** `main` (dirty) · **HEAD:** `364180d…d1b851`

## 1. Frozen Phase 3 Input Contract (consumed by Phase 4)

| Item | Identity | Value |
|---|---|---|
| Corpus | `agent-research-corpus-v1` | `corpus_sha256=3d0e034c0155e4d3190155137a0d312e4c156f80fb2be89215b4b2daaef788d7` |
| Corpus source | `web-agent-frameworks-v1` | `content_sha256=794bed8459aca36698d8fe6bb2b749c0ff003d0e36ff629cbae51536f314ddeb` |
| Corpus source | `catalog-frameworks-v1` | `content_sha256=aa8005363b8a0dd8e9e118797fca644ac7745edf7456864c7261557dfac7bbcb` |
| Corpus source | `knowledge-evaluation-notes-v1` | `content_sha256=fea0ad2368c20d6c1e9e8f1e02759d13b0598d001448d70c991e60626690d6c6` |
| Dataset | `seed-10-v1` | 10 cases `seed-001…seed-010`; `file_sha256=a902aba483f89285b02792369963ce5edb35f3460abfdcc1b7f712b0e8cf1055` |
| Dataset | `dev-40-v1` | 40 cases `dev-001…dev-040`; `file_sha256=2a1aab55016a1fdb7f9fa56c2fc309d351f113f9d8f68951f1ca2eeebf34223f` |
| Runner | `runner_version=1.0.0` | `execution_mode=offline`, `model_id=mock:deterministic` |
| Strategy | `s0-single-agent` | `prompt_id=s0-single-agent-v1`; `prompt_sha256=3cf9f8379e16c866d9829792779d957266034dfd72f518d5e807bca6c1facb03`; `config_sha256=1fdff00f40ad28436b7c0995816575e30de004e7ace112e0a677ba0a0b8cc759` |
| Strategy | `s1-orchestrator-workers` | `prompt_id=s1-orchestrator-workers-v1`; `prompt_sha256=8538a539e06166341c13bc1c62443973f3d7334bf000802401a2d3c228bf4e94`; `config_sha256=2f8a99c0fb77d9ce0d71082a953fff30679782ddf91dbfbb8cd0724e004d0487` |

Report contract (frozen): `EvaluationCase` / `StrategyOutput` / `CaseResult` /
`RunManifest` / `EvaluationReport`, with a 17-field manifest, canonical SHA-256
run/input fingerprints, dirty-worktree marker, and strict offline/real
separation. Phase 4 consumes this contract and adds claim/evidence/citation
implementation; it must not modify the frozen corpus/dataset/runner/report
contract or product code.

## 2. Fresh Gate Results — 2026-08-08 (P3-7, HEAD `364180d` dirty worktree)

| Gate | Exit | Result |
|------|------|--------|
| `.venv/bin/python -m pytest tests/e2e/phase3/test_agent_research_closure.py -q` | 0 | 2 passed (agent-research API/WS/artifact closure) |
| `.venv/bin/python -m pytest tests/e2e/phase3 tests/integration/phase3 tests/unit/phase3 -q` | 0 | 301 passed, 2 skipped (complete Phase 3) |
| `.venv/bin/python -m pytest tests/ -q` | 0 | 741 passed, 13 skipped (complete backend, incl. Phase 2 regression) |
| `pnpm --dir frontend exec vitest run` | 0 | 60 passed (1 file) |
| `pnpm --dir frontend exec eslint src` | 0 | clean |
| `pnpm --dir frontend run build` | 0 | `tsc -b && vite build` — JS 155.92 kB / CSS 4.50 kB gzip (byte-identical to Phase 2 accepted evidence) |
| `.venv/bin/ruff check app tests scripts` | 0 | clean |
| `.venv/bin/ruff format --check app tests scripts` | 0 | 98 files already formatted |
| `git diff --check` | 0 | clean |

The gates modified no files (`git status` before/after identical). The
`StarletteDeprecationWarning` (httpx + starlette.testclient) persists in
backend runs — non-blocking, unchanged from Phase 2.

**Phase 2 vs Phase 3 distinction:** the Phase 2 release evidence (accepted at
`364180d`, tag `v0.1.1-tutorial-parity`) is separate and remains valid; the
table above is a **fresh Phase 3 acceptance run** on the uncommitted worktree.
Phase 2 backend/React regression is included in the `tests/ -q` (741 passed /
13 skipped) and frontend rows.

## 3. Reproducibility — Fresh seed-10 / dev-40 S0/S1 Offline Reports (×2)

Both datasets × both strategies were run **twice** into fresh directories under
`/private/tmp` (`p3-rerun-a`, `p3-rerun-b`) with
`scripts/evaluate.py --offline`; all 8 runs exited 0. Comparison of run A vs
run B per dataset/strategy:

| Dataset/strategy | Terminal case rows | `cases.jsonl` A vs B | Stable manifest fields (excl. `run_id`/`started_at`) | `run_fingerprint` | `input_fingerprint` |
|---|---|---|---|---|---|
| seed-10 / s0 | 10, all `success` | byte-identical | identical | `21d567b1e762ce624f31bee95501f70cbc9b67e3aa4da2d837e93675c44a0676` | `3510a4112b4c96bec39d7382c98cf2999d61f1700d7bb3e3c5e1c9987187704f` |
| seed-10 / s1 | 10, all `success` | byte-identical | identical | `e1822980111ea01aeb339b6b884638b0ecb8e552937f5f4e7ec4509b1b216b2c` | `6e6d6b5cd6debc5db3e421e06abc169a94d29ffc5ea8c964805fc30b990fd24a` |
| dev-40 / s0 | 40, all `success` | byte-identical | identical | `abe08df13c822473437937560e738ec447dc70f1ce73056fcc814f2e069a3477` | `76e617bd9ca4b5d278e22c148ec653ff90a2baed72fa8c7cf9d367eccca7d495` |
| dev-40 / s1 | 40, all `success` | byte-identical | identical | `778d8e338051e4f0c51ca3a55caaa72ac9f8096b6582cd9e73e89219c88d24d8` | `e570f88a8abf1927c9c52c5ef68a721228ef9aafef5479a06aa2d1de8806cc83` |

- Every manifest records `git_commit=364180d54a4c7b3141147f58b64b8ddd47d1b851`
  and `git_dirty=true` (dirty worktree is truthfully marked, never presented as
  a clean checkpoint).
- Only volatile fields differ between runs: `run_id` (fresh UUID per run);
  `started_at` happened to fall in the same second and was identical — it is
  excluded from fingerprints by design.
- `summary.md` between run A and B differs only in the `run_id` line.
- `--compare` runs (seed-10 and dev-40) produced `comparison.md` with
  identical comparable fingerprints (dataset/corpus/model/execution),
  strategy-differing prompt/config fields, and the explicit note *"No
  superiority claim is made: all numbers are deterministic offline proxies and
  never real Provider quality."*

## 4. Offline Aggregates, Cost and Latency (fresh rerun A)

| Dataset/strategy | total | success | failed | skipped | success_rate | topic_recall_mean | source_coverage_mean | latency | cost_total_usd |
|---|---|---|---|---|---|---|---|---|---|
| seed-10 / s0 | 10 | 10 | 0 | 0 | 1.0 | 0.7167 | 1.0 | `n/a` | 0.0 |
| seed-10 / s1 | 10 | 10 | 0 | 0 | 1.0 | 0.7167 | 1.0 | `n/a` | 0.0 |
| dev-40 / s0 | 40 | 40 | 0 | 0 | 1.0 | 0.6083 | 1.0 | `n/a` | 0.0 |
| dev-40 / s1 | 40 | 40 | 0 | 0 | 1.0 | 0.6083 | 1.0 | `n/a` | 0.0 |

Offline semantics are truthful: every case row has `latency_ms=null` (rendered
`n/a`, never a fabricated number) and `cost_usd=0.0` (the known deterministic
mock cost). No real Provider quality is claimed anywhere.

## 5. Real Provider / Model Smokes — Skipped, Never GREEN

Both real smoke files were run with opt-in flags absent; no credentials were
accessed and no network call was made:

| File | Exit | Result |
|---|---|---|
| `tests/integration/phase3/test_real_model_smoke.py` | 0 | 1 skipped: `PHASE3_REAL_MODEL_SMOKE is not set to '1': real model smoke is opt-in and stays skipped; no credentials were accessed and no network call was made` |
| `tests/integration/phase3/test_real_provider_smoke.py` | 0 | 1 skipped: `PHASE3_REAL_PROVIDER_SMOKE is not set to '1': real Provider smoke is opt-in and stays skipped; no credentials were accessed and no network call was made` |

No real smoke is reported as GREEN. A real run requires the user to explicitly
set the opt-in flag **and** have the credential already configured outside the
repository.

## 6. Report Hygiene Scan

All generated artifacts (8 × `manifest.json`/`cases.jsonl`/`summary.md` plus 2
× `comparison.md`, including per-strategy sub-reports) were scanned for
credential patterns, absolute/local filesystem paths (POSIX/Windows) and raw
Provider response markers: **0 hits**. Reports contain only relative artifact
paths and deterministic offline content.

## 7. Known Limitations and Unresolved Risks

- **Dirty worktree:** acceptance evidence is bound to the uncommitted Phase 3
  worktree at `364180d` with `git_dirty=true`. A clean checkpoint commit,
  tag/push/release, and Phase 4 activation require later explicit user
  authorization; nothing was committed, tagged, pushed or released by this
  node.
- **Real smokes:** remain skipped (opt-in flags and credentials absent); no
  real-model/real-Provider numbers exist yet.
- **Structured worker limitations:** dev-40 S1 reports surface per-worker
  limitation entries (e.g. `worker web_snapshot skipped: no allowed
  web_snapshot sources for this case`); cases themselves remain terminal
  `success` and no unsupported superiority claim is made.
- `StarletteDeprecationWarning` in backend pytest runs (non-blocking; matches
  Phase 2).
