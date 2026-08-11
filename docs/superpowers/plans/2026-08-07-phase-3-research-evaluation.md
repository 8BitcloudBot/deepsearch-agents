# Phase 3 Research Evaluation Implementation Plan

> **Historical plan:** Phase 3 is accepted. Provider names and collaboration
> instructions below are retained for audit only and are not current route or
> execution guidance.

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Each package
> is a separate fresh Reasonix node and requires independent Codex acceptance
> before the next package starts.

**Goal:** Add an `agent-research` profile and produce reproducible S0 Single
Agent and S1 Orchestrator-Workers evaluation baselines on fixed AI Agent
research datasets without regressing the accepted tutorial product flow.

**Architecture:** Keep the Phase 2 API, WebSocket, artifact, task lifecycle and
React workbench as the product shell. Add a small `app/research` domain module
for versioned local sources and the agent-research runtime, plus a separate
`app/evaluation` module for dataset loading, strategy execution, fingerprinting
and reports. Offline deterministic runs are mandatory; real Provider/model
runs are opt-in and reported separately.

**Tech Stack:** Python 3.12, FastAPI, existing DeepAgents/LangGraph adapters,
Pydantic/dataclasses, JSON/JSONL/Markdown versioned fixtures, pytest, Ruff,
pre-commit, existing React/Vitest regression suite.

## Global Constraints

- Entry baseline is annotated release `v0.1.1-tutorial-parity`, peeled to
  `364180d54a4c7b3141147f58b64b8ddd47d1b851`.
- `APP_PROFILE=tutorial` remains the default; all Phase 2 API, WebSocket,
  artifact, security and React contracts remain green.
- `APP_PROFILE=agent-research` is additive and uses the same HTTP/WS shell.
- Offline/mock evidence and real Provider/model evidence use separate run
  manifests and separate aggregate rows.
- Every metric binds dataset ID/hash, source corpus ID/hash, strategy, model,
  Prompt, configuration and Git commit.
- No credentials, production data or unreviewed live content enter versioned
  fixtures or reports.
- Phase 3 does not implement citation entailment, S2-S4, production trace,
  persistence/recovery, approval state machines or budget enforcement.
- Reasonix nodes do not commit, tag, push, release or alter `.reasonix/`.

## Accepted Phase 2 Contract Boundary

The following interfaces are reused rather than replaced:

- HTTP: `POST /api/upload`, `POST /api/task`,
  `POST /api/task/{thread_id}/cancel`, `GET /api/files`,
  `GET /api/download`, `GET /health`.
- WebSocket: `/ws/{thread_id}` with version-1 events, per-thread monotonic
  sequence, bounded subscribers and exactly one terminal event.
- Runtime seam: `RuntimeRequest`, `RuntimeResult`, and an async
  `run(request) -> RuntimeResult` implementation injected into `TaskRegistry`.
- Artifacts: relative, per-thread Markdown/PDF files generated atomically and
  listed/downloaded by the existing endpoints.
- Frontend: renders additive event data and server-returned relative artifact
  paths; Phase 3 does not require a new React application.

## Phase 3 Data Contracts

### Versioned source manifest

`data/phase3/sources/manifest.json`:

```json
{
  "corpus_id": "agent-research-corpus-v1",
  "schema_version": 1,
  "captured_at": "2026-08-07",
  "sources": [
    {
      "source_id": "web-deepagents-overview-v1",
      "kind": "web_snapshot",
      "path": "web/deepagents-overview.json",
      "content_sha256": "64 lowercase hex characters"
    }
  ]
}
```

Each source record exposes `source_id`, `kind` (`web_snapshot`, `catalog`, or
`knowledge`), `title`, `origin`, `captured_at`, `content`, and
`content_sha256`. Loaders reject duplicate IDs, path escape, hash mismatch,
unknown fields and non-UTF-8 text.

### Evaluation case

Each JSONL line in `data/phase3/datasets/*.jsonl` contains:

```json
{
  "case_id": "seed-001",
  "split": "seed",
  "question": "Compare two agent orchestration approaches.",
  "expected_topics": ["orchestrator-workers", "single-agent"],
  "allowed_source_ids": ["web-deepagents-overview-v1"],
  "difficulty": "basic"
}
```

### Evaluation output

- `RunManifest`: `run_id`, `runner_version`, `execution_mode`, `strategy_id`,
  `dataset_id`, `dataset_sha256`, `corpus_id`, `corpus_sha256`, `model_id`,
  `prompt_id`, `prompt_sha256`, `config_sha256`, `git_commit`, `started_at`.
- `CaseResult`: `case_id`, `status` (`success`, `failed`, `skipped`),
  `answer`, `artifact_paths`, `latency_ms`, `cost_usd`, `tool_calls`,
  `topic_recall`, `source_coverage`, `error_code`, `limitations`.
- `EvaluationReport`: manifest, ordered case results, aggregate counts/rates,
  latency summary, cost summary, limitations and explicit skipped reasons.
- Offline deterministic mode uses `model_id="mock:deterministic"`,
  `cost_usd=0`, and never claims real Provider quality.

## Package Order And Dependencies

```text
P3-1 Agent-Research Vertical Slice
  -> P3-2 Versioned Corpus + seed-10
     -> P3-3 Unified Runner + S0
        -> P3-4 S1 Orchestrator-Workers
           -> P3-5 dev-40 Promotion
              -> P3-6 Fingerprints, Reports + Opt-In Smokes
                 -> P3-7 Integrated Acceptance + Phase 4 Handoff
```

---

## P3-1 — Minimal Agent-Research Vertical Slice

1. **Single goal.** Run one deterministic AI Agent research question through
   `APP_PROFILE=agent-research`, the existing API/task/event shell, all three
   offline source families, and Markdown/PDF artifact download.
2. **Prerequisites.** Release `v0.1.1-tutorial-parity`; no dataset runner or
   real Provider credentials.
3. **Included / excluded.** Include profile selection, one curated source per
   source family, an offline research runtime, report content and one vertical
   E2E. Exclude seed-10, evaluation scoring, S1, frontend redesign and live
   network ingestion.
4. **Allowed modules.** Modify `app/settings.py`, `app/main.py`,
   `app/api/server.py`; create `app/research/__init__.py`,
   `app/research/contracts.py`, `app/research/corpus.py`,
   `app/research/runtime.py`, `data/phase3/sources/manifest.json`,
   `data/phase3/sources/web/agent-frameworks.json`,
   `data/phase3/sources/catalog/frameworks.json`,
   `data/phase3/sources/knowledge/evaluation-notes.md`,
   `tests/unit/phase2/test_remediation_2.py`,
   `tests/unit/phase3/test_research_profile.py`,
   `tests/integration/phase3/test_research_runtime.py`, and
   `tests/e2e/phase3/test_agent_research_closure.py`.
5. **Data / API contract.** `APP_PROFILE` accepts `tutorial|agent-research`;
   tutorial remains default. `AgentResearchRuntime.run(RuntimeRequest)` returns
   `RuntimeResult` and writes the existing `tutorial-report.md/.pdf` artifact
   names so the accepted frontend/download contract remains unchanged. Reports
   add `profile: agent-research`, corpus ID and source modes.
6. **Safety / reproducibility invariants.** No network; manifest paths remain
   under `data/phase3/sources`; source hashes are verified; uploaded content
   remains untrusted; terminal ownership stays in `TaskRegistry`; tutorial
   health/defaults remain byte-for-byte compatible except additive
   `app_profile` metadata.
7. **RED → GREEN.** First add failing settings, corpus validation, runtime and
   E2E tests. Run
   `.venv/bin/python -m pytest tests/unit/phase3/test_research_profile.py tests/integration/phase3/test_research_runtime.py tests/e2e/phase3/test_agent_research_closure.py -q`
   and require failures for missing profile/runtime. Implement the minimum and
   rerun to green, then run the accepted Phase 2 E2E and frontend tests.
8. **Minimum E2E evidence.** Upload a unique constraint, start an
   agent-research task, observe Web/Catalog/Knowledge tool events and exactly
   one `task_completed`, list/download both artifacts, and find the unique
   marker plus corpus ID in Markdown.
9. **Definition of done.** Both profiles start independently; Phase 2
   regression gates remain green; the agent-research E2E is deterministic and
   no evaluation score is claimed.
10. **Bounded Reasonix node.** Goal: implement only this vertical slice.
    File whitelist is exactly the paths in item 4. Forbidden: frontend changes,
    dependencies, CI, seed/dev datasets, evaluation runner, real providers,
    commits/tags/pushes. The only permitted Phase 2 test change is to replace
    the stale tutorial-only profile assertion with acceptance of `tutorial` and
    `agent-research` while continuing to reject every other profile. Final
    report: changed files, RED, GREEN, Phase 2 regression, unresolved risks;
    maximum 10 lines.

## P3-2 — Versioned Corpus And seed-10 Dataset

1. **Single goal.** Freeze a validated v1 research corpus and ten deterministic
   evaluation cases before building the runner.
2. **Prerequisites.** P3-1 accepted and its source loader contract stable.
3. **Included / excluded.** Include curated Web snapshots, structured catalog,
   knowledge notes, source manifest, seed-10 JSONL and validators. Exclude
   dev-40, scoring, strategy execution and live fetchers.
4. **Allowed modules.** Modify `app/research/contracts.py`,
   `app/research/corpus.py`, `data/phase3/sources/**`; create
   `app/evaluation/__init__.py`, `app/evaluation/contracts.py`,
   `app/evaluation/datasets.py`, `data/phase3/datasets/seed-10.jsonl`,
   `data/phase3/datasets/manifest.json`,
   `tests/unit/phase3/test_source_corpus.py`, and
   `tests/unit/phase3/test_seed_dataset.py`.
5. **Data / API contract.** Corpus and case schemas are the contracts above.
   Dataset manifest records `dataset_id="seed-10-v1"`, schema version, case
   count 10, file SHA-256 and corpus ID. Case IDs are unique and sorted.
6. **Safety / reproducibility invariants.** Fixtures contain no credentials,
   executable instructions or unbounded HTML; every source and dataset file is
   hashed; loaders reject unknown source IDs and traversal; source capture date
   and origin are explicit.
7. **RED → GREEN.** Write failing tests for exact count, unique IDs, stable
   ordering, hash mismatch, unknown source, invalid split and forbidden path.
   Run `.venv/bin/python -m pytest tests/unit/phase3/test_source_corpus.py tests/unit/phase3/test_seed_dataset.py -q`,
   then implement loaders/data until green.
8. **Minimum E2E evidence.** Extend the P3-1 E2E to load one case by ID from
   seed-10 and run it through the same offline runtime without changing API
   endpoints.
9. **Definition of done.** Ten cases validate deterministically; corpus and
   dataset hashes are reproducible from a clean checkout; no metric result is
   generated yet.
10. **Bounded Reasonix node.** Whitelist only item 4 plus the existing P3-1 E2E
    test for the one-case proof. Forbidden: runner, S0/S1 reports, network,
    dependencies, docs status changes, commits/tags/pushes.

## P3-3 — Unified Evaluation Runner And S0 Baseline

1. **Single goal.** Prove a unified offline runner by executing all seed-10
   cases with S0 Single Agent and emitting machine-readable plus Markdown
   reports.
2. **Prerequisites.** P3-2 accepted; seed-10 and corpus hashes fixed.
3. **Included / excluded.** Include runner CLI, S0 strategy, result aggregation,
   deterministic metrics and failure/skip handling. Exclude S1, dev-40, real
   model runs and citation scoring.
4. **Allowed modules.** Modify `app/evaluation/contracts.py`,
   `app/evaluation/datasets.py`; create `app/evaluation/runner.py`,
   `app/evaluation/strategies/__init__.py`,
   `app/evaluation/strategies/s0_single_agent.py`,
   `app/evaluation/reporting.py`, `scripts/evaluate.py`,
   `tests/unit/phase3/test_evaluation_runner.py`,
   `tests/unit/phase3/test_s0_strategy.py`, and
   `tests/integration/phase3/test_seed10_s0.py`.
5. **Data / API contract.** `EvaluationStrategy.run(case, corpus) ->
   StrategyOutput`; CLI accepts `--dataset seed-10 --strategy s0 --offline
   --output <dir>`. It writes `manifest.json`, `cases.jsonl`, and `summary.md`
   under the requested output directory.
6. **Safety / reproducibility invariants.** Case order is stable; one case
   failure does not abort later cases; exception text is redacted; skipped is
   distinct from failed; offline cost is zero; report paths are relative; the
   runner never writes into versioned data directories.
7. **RED → GREEN.** Add failing tests for ordered execution, result statuses,
   aggregate counts, output files and deterministic reruns. Run
   `.venv/bin/python -m pytest tests/unit/phase3/test_evaluation_runner.py tests/unit/phase3/test_s0_strategy.py tests/integration/phase3/test_seed10_s0.py -q`,
   then implement the minimum runner/S0.
8. **Minimum E2E evidence.** Run
   `.venv/bin/python scripts/evaluate.py --dataset seed-10 --strategy s0 --offline --output /tmp/phase3-s0`
   twice and prove identical case statuses/metrics/fingerprints except run ID and
   timestamps.
9. **Definition of done.** seed-10 produces ten terminal case results and an
   aggregate S0 report with success, failed, skipped, latency, zero offline
   cost and limitations; no S1 code exists.
10. **Bounded Reasonix node.** Whitelist item 4 and no other source/data files.
    Use seed-10 read-only. Forbidden: S1, dev-40, API/frontend changes, real
    providers, CI, commits/tags/pushes.

## P3-4 — S1 Orchestrator-Workers Baseline

1. **Single goal.** Add S1 behind the same runner and compare it with S0 on
   seed-10 under identical corpus, metrics and offline configuration.
2. **Prerequisites.** P3-3 accepted; runner and S0 contracts frozen.
3. **Included / excluded.** Include one orchestrator and three bounded workers
   (Web snapshot, catalog, knowledge), additive strategy selection and a
   comparison report. Exclude S2-S4, reviewers, routing experiments and live
   providers.
4. **Allowed modules.** Create
   `app/evaluation/strategies/s1_orchestrator_workers.py`,
   `tests/unit/phase3/test_s1_strategy.py`,
   `tests/integration/phase3/test_seed10_s1.py`, and
   `tests/integration/phase3/test_seed10_strategy_comparison.py`; modify only
   `app/evaluation/strategies/__init__.py`, `app/evaluation/runner.py`,
   `app/evaluation/reporting.py`, and `scripts/evaluate.py`.
5. **Data / API contract.** Strategy ID is `s1-orchestrator-workers`. Worker
   outputs contain `worker_id`, ordered `source_ids`, `summary`, `latency_ms`
   and `status`; orchestrator output conforms to the same `StrategyOutput` used
   by S0.
6. **Safety / reproducibility invariants.** Workers receive only allowed source
   IDs; worker failures become structured limitations; merge ordering is
   deterministic; S0 code/results are unchanged; no parallel timing is used as
   a quality claim in offline mode.
7. **RED → GREEN.** Add failing tests for worker boundaries, stable merge,
   partial worker failure and same-runner compatibility. Run the three new test
   files, implement S1, then rerun all P3-3 tests.
8. **Minimum E2E evidence.** Execute seed-10 S0 and S1 with the same output root
   and produce a comparison table keyed by identical fingerprint fields except
   strategy ID; every case must have a terminal result in both runs.
9. **Definition of done.** S1 runs through the unchanged CLI/runner; comparison
   reports quality proxies, latency and limitations without claiming S1 wins
   unless measured values show it.
10. **Bounded Reasonix node.** Whitelist item 4. Seed/corpus are read-only.
    Forbidden: dataset edits, S2-S4, real model/provider calls, API/frontend,
    dependencies, commits/tags/pushes.

## P3-5 — dev-40 Dataset Promotion

1. **Single goal.** Expand the fixed evaluation set from seed-10 to dev-40 and
   prove both accepted strategies complete it under the same protocol.
2. **Prerequisites.** P3-4 accepted; S0/S1 runner compatibility proven on
   seed-10.
3. **Included / excluded.** Include forty curated cases, dataset manifest/hash,
   validation and offline S0/S1 integration evidence. Exclude test-set tuning,
   new metrics and strategy changes motivated only by dev cases.
4. **Allowed modules.** Create `data/phase3/datasets/dev-40.jsonl`,
   `tests/unit/phase3/test_dev_dataset.py`,
   `tests/integration/phase3/test_dev40_s0.py`, and
   `tests/integration/phase3/test_dev40_s1.py`; modify
   `data/phase3/datasets/manifest.json` and, only for dataset selection,
   `app/evaluation/datasets.py` and `scripts/evaluate.py`.
5. **Data / API contract.** Dataset ID is `dev-40-v1`, exact count 40, split
   `dev`, stable case IDs `dev-001` through `dev-040`, and the same case schema
   as seed-10.
6. **Safety / reproducibility invariants.** dev-40 uses only versioned source
   IDs; does not contain expected model prose; case changes require manifest
   hash changes; seed-10 remains immutable.
7. **RED → GREEN.** Add failing exact-count/hash/coverage tests and integration
   tests that initially reject missing dev-40. Add cases, validate, then run S0
   and S1 dev-40 integrations.
8. **Minimum E2E evidence.** Two offline CLI runs:
   `--dataset dev-40 --strategy s0` and `--dataset dev-40 --strategy s1`, each
   yielding exactly 40 terminal case rows and no silent omissions.
9. **Definition of done.** dev-40 validates and both strategies finish; changes
   to algorithms or thresholds are not hidden inside the dataset package.
10. **Bounded Reasonix node.** Whitelist item 4. Forbidden: modifying seed-10,
    strategies beyond dataset selection compatibility, real providers,
    dependencies, docs/status, commits/tags/pushes.

## P3-6 — Fingerprints, Truthful Reports And Opt-In Real Smokes

1. **Single goal.** Make every S0/S1 result auditable and add explicitly gated
   real Provider/model smoke paths without mixing them with offline results.
2. **Prerequisites.** P3-5 accepted; seed-10/dev-40 and S0/S1 stable.
3. **Included / excluded.** Include full fingerprints, cost/latency/status
   reporting, limitations, redaction and opt-in smoke tests. Exclude production
   tracing, budgets, persistent run storage and claims/citations.
4. **Allowed modules.** Create `app/evaluation/fingerprint.py`,
   `tests/unit/phase3/test_fingerprint.py`,
   `tests/unit/phase3/test_evaluation_reporting.py`,
   `tests/integration/phase3/test_real_provider_smoke.py`, and
   `tests/integration/phase3/test_real_model_smoke.py`; modify
   `app/evaluation/contracts.py`, `app/evaluation/runner.py`,
   `app/evaluation/reporting.py`, `scripts/evaluate.py`, and `.env.example`.
5. **Data / API contract.** Fingerprints use SHA-256 over canonical JSON with
   sorted keys. Real runs require `PHASE3_REAL_PROVIDER_SMOKE=1` or
   `PHASE3_REAL_MODEL_SMOKE=1` plus existing credentials. Missing flags or
   credentials produce explicit pytest skips and report status `skipped`.
6. **Safety / reproducibility invariants.** Manifests contain model/provider
   identifiers but never keys, base-url credentials, raw provider responses or
   absolute paths. Unknown cost is `null`, never zero. Offline and real rows
   have distinct `execution_mode` values.
7. **RED → GREEN.** Add failing tests for canonical hashes, dirty-worktree
   marker, redaction, cost-null behavior and explicit skips. Implement, then
   run the complete Phase 3 unit/integration suite without credentials and
   verify the real tests report skipped rather than passed.
8. **Minimum E2E evidence.** Generate seed-10 and dev-40 offline S0/S1 reports;
   verify every report contains all fingerprint fields and limitations. Run the
   real smoke test files without credentials and record exact skip reasons.
9. **Definition of done.** All reported numbers have reproducible provenance;
   failed/skipped cases remain visible; real evidence is absent unless an
   opt-in run actually completes.
10. **Bounded Reasonix node.** Whitelist item 4. Provider network use is allowed
    only when the user separately authorizes a real smoke and credentials are
    already configured outside the prompt. Forbidden: credentials in files,
    CI secrets, production data, trace/persistence/governance, commits/tags.

## P3-7 — Integrated Acceptance And Phase 4 Handoff

1. **Single goal.** Independently accept Phase 3, publish canonical evidence,
   and freeze the exact dataset/runner boundary consumed by Phase 4.
2. **Prerequisites.** P3-1 through P3-6 independently accepted.
3. **Included / excluded.** Include full regression/evaluation gates,
   reproducibility reruns, evidence, limitations and Phase 4 dependency notes.
   Exclude product implementation, citation metrics, S2-S4 and release/tag
   operations.
4. **Allowed modules.** Modify only `docs/phase-status.md`, `docs/roadmap.md`,
   `docs/phases/phase-3-research-evaluation.md`,
   `docs/phases/phase-4-trustworthy-citations.md`, and create
   `docs/verification/phase-3-evidence.md`.
5. **Data / API contract.** Evidence records exact commit, dataset/corpus
   hashes, runner version, S0/S1 manifests, commands, exit codes, case counts,
   skipped real smokes and Phase 2 regression totals.
6. **Safety / reproducibility invariants.** No future phase is marked complete;
   no absent real smoke is reported as green; generated reports are checked for
   secrets, absolute paths and raw provider responses; accepted Phase 2 remains
   reproducible.
7. **RED → GREEN.** Run Phase 3 tests and the accepted Phase 2 backend/frontend
   gates. Run seed-10 and dev-40 S0/S1 twice and compare stable fingerprinted
   fields. Any mismatch is RED and blocks status updates.
8. **Minimum E2E evidence.** One agent-research API closure plus four runner
   executions (seed S0/S1, dev S0/S1), with every case terminal and reports
   downloadable/readable.
9. **Definition of done.** Phase 3 status is accepted only after Codex reviews
   the full diff and reruns gates; Phase 4 receives fixed dataset/runner inputs;
   no tag or release is created without later explicit authorization.
10. **Bounded Reasonix node.** Documentation/evidence whitelist is exactly item
    4. Reasonix may run read-only gates but may not modify source/tests/data,
    commit, tag, push, release, access credentials or start Phase 4.

## Recommended First Reasonix Node

Start with **P3-1 — Minimal Agent-Research Vertical Slice** after the decisions
below are confirmed. Its exact file whitelist is:

- `app/settings.py`
- `app/main.py`
- `app/api/server.py`
- `app/research/__init__.py`
- `app/research/contracts.py`
- `app/research/corpus.py`
- `app/research/runtime.py`
- `data/phase3/sources/manifest.json`
- `data/phase3/sources/web/agent-frameworks.json`
- `data/phase3/sources/catalog/frameworks.json`
- `data/phase3/sources/knowledge/evaluation-notes.md`
- `tests/unit/phase2/test_remediation_2.py`
- `tests/unit/phase3/test_research_profile.py`
- `tests/integration/phase3/test_research_runtime.py`
- `tests/e2e/phase3/test_agent_research_closure.py`

The node must first demonstrate RED for the missing profile/runtime, then GREEN
for the one-question offline closure, and finally rerun the Phase 2 E2E plus
frontend Vitest regression. It must not add evaluation abstractions that are not
used by this slice.

## Confirmed Long-Range Decisions

Confirmed by the user on 2026-08-08. These choices apply to P3-1 through P3-7.

1. **Offline baseline policy — recommended:** deterministic offline S0/S1 is
   mandatory and accepted without external credentials; real runs are separate
   optional evidence, never release blockers.
2. **Artifact compatibility — recommended:** keep `tutorial-report.md/.pdf` for
   both profiles during Phase 3 so the existing React/API contract is reused;
   distinguish profiles inside content and manifests rather than filenames.
3. **Dataset content policy — recommended:** version only curated AI Agent
   framework/evaluation material with stable origin and capture date; do not
   auto-ingest live pages during evaluation.
4. **Quality thresholds — recommended:** Phase 3 reports measured topic recall,
   source coverage and task success but does not declare an arbitrary S1 win
   threshold before seed-10 results exist.
5. **Generated output policy — recommended:** runner outputs go to a caller
   supplied ignored directory; only schemas, fixed datasets and accepted summary
   evidence are versioned.
6. **Real Provider authorization:** confirm whether later P3-6 may use configured
   Tavily/RAGFlow/model credentials and provider network, or must remain skip-only.
7. **React scope — recommended:** no Phase 3 UI redesign; the accepted workbench
   remains the E2E shell, and evaluation reports are CLI/evidence artifacts.

## Execution Progress

- **P3-1: accepted.** Codex independently verified Phase 3 targeted `44 passed`,
  complete backend `484 passed / 11 skipped`, React `60 passed`, Ruff check and
  format, `git diff --check`, real `/ws/{thread_id}` event delivery, one terminal,
  two-thread isolation, report redaction and residual-provider-env offline startup.
- **P3-2: accepted.** Codex independently verified exact seed-10 IDs/count,
  corpus/source references and hashes, strict UTF-8, metadata consistency,
  schema/path rejection, complete backend `564 passed / 11 skipped`, React
  `60 passed`, Ruff check/format and `git diff --check`.
- **P3-3: accepted.** Codex independently verified targeted `73 passed`, full
  Phase 3 `197 passed`, complete backend `637 passed / 11 skipped`, Ruff
  check/format and `git diff --check`. Two fresh CLI runs produced byte-identical
  case rows and identical stable manifest fields; cross-cwd invocation bound the
  checkout HEAD; versioned `data/phase3` (including a resolved symlink alias)
  was rejected as an output target before write. P3-4 is the only ready package.
- **P3-4: accepted.** Codex independently verified focused P3-4 `41 passed`,
  P3-3 regression `73 passed`, full Phase 3 `238 passed`, complete backend
  `678 passed / 11 skipped`, Ruff check/format and `git diff --check`. S1 has
  exactly three fixed-role workers; topology and outputs fail closed, and a
  malformed worker cannot claim unauthorized sources or pollute metrics. The
  seed-10 CLI comparison produced ten ordered terminal rows for both S0/S1 on
  identical input fingerprints with truthful unavailable latency, zero offline
  cost and no unsupported superiority claim. P3-5 is the only ready package.
- **P3-5: accepted.** Codex independently verified targeted registry/dev tests
  `71 passed`, full Phase 3 `271 passed`, complete backend `711 passed / 11
  skipped`, Ruff check/format and `git diff --check`. The strict registry now
  validates immutable seed-10 plus dev-40; seed remains byte-identical. Fresh
  S0, S1 and comparison CLI runs each completed all 40 ordered dev cases on the
  same input fingerprints with zero offline cost and unavailable latency. P3-6
  is the only ready package.
- **P3-6: accepted.** Codex independently verified targeted P3-6 `30 passed / 2
  skipped`, full Phase 3 `301 passed / 2 skipped`, complete backend `741
  passed / 13 skipped`, Ruff check/format and `git diff --check`. Canonical
  SHA-256, dirty marker, full input/run fingerprints, redaction and truthful
  unknown-cost null semantics are covered. Both real smoke suites explicitly
  skipped without opt-in flags and made no network call. Seed-10/dev-40 S0/S1
  offline reports contain complete terminal rows and fingerprints. P3-7 is the
  only ready package.

## Phase 4–8 Dependency Boundaries

- **Phase 4 citations:** consumes the frozen Phase 3 corpus, datasets, case
  results and report schema; claim extraction, evidence matching and citation
  entailment remain Phase 4 work.
- **Phase 5 orchestration:** consumes measured S0/S1 baselines; S2-S4,
  reviewers, routing experiments and ablations remain Phase 5 work.
- **Phase 6 observability:** consumes stable run/case/strategy identifiers;
  production traces, dashboards and operational telemetry remain Phase 6 work.
- **Phase 7–8 reliability/governance:** persistence, recovery, approvals and
  budget enforcement remain later-phase concerns. Phase 3 adds no speculative
  framework for them.

## Planning Self-Review

- Coverage: all requested deliverables map to P3-1 through P3-7.
- Ordering: vertical slice precedes abstractions; seed-10 precedes runner/S0;
  S0 precedes S1; dev-40 follows both strategies.
- Scope: Phase 4 citation validation, Phase 5 S2-S4, Phase 6 production trace,
  and Phase 7-8 reliability/governance remain dependency boundaries only.
- Reproducibility: every metric contract carries dataset, corpus, strategy,
  model, Prompt, configuration and commit identity.
- Placeholder scan: the plan contains no unresolved implementation placeholders.
