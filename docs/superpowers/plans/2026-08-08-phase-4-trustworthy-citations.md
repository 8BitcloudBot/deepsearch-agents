# Phase 4 Trustworthy Citations Implementation Plan

**Status:** P4-1 through P4-7 accepted and frozen at closeout checkpoint
`acf7c46` (implementation checkpoint `e817c79`). Phase 5 is not started.

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Each
> package is a separate fresh Reasonix node and requires independent Codex
> acceptance before the next package starts.

**Goal:** Add a reproducible citation layer that maps report claims to versioned
source evidence, distinguishes rule support from semantic support, reports
citation quality metrics, and exposes the result through the existing API,
WebSocket stream, and React workbench without regressing the accepted tutorial
or agent-research flows.

**Architecture:** Treat the Phase 3 corpus, datasets, runner, and report
contracts as read-only inputs. Add a focused `app/citations` domain for claims,
evidence spans, support judgments, and citation reports; use deterministic
rule checks offline and an explicitly opt-in semantic adapter whose skipped
state is never merged into mock quality claims. Integrate citation results as
additive task artifacts, non-terminal events, and a small React panel that
renders server-validated data as text.

**Tech Stack:** Python 3.12, FastAPI/Pydantic, existing in-memory event bus and
TaskRegistry, JSON/JSONL/Markdown fixtures, pytest, Ruff, pre-commit, React,
TypeScript, Vitest and existing Vite build.

## Global Constraints

- Entry baseline is clean checkpoint `8afa4cd84cdf3da4259b3570011c7d1d923fbd8e`.
- `APP_PROFILE=tutorial` remains the default and its Phase 2 HTTP, WebSocket,
  artifact, security, and React contracts remain green.
- `APP_PROFILE=agent-research` remains runnable and consumes the unchanged
  Phase 3 corpus/dataset/runner/report contracts.
- Phase 3 files under `data/phase3/**`, `app/evaluation/**`, and the frozen
  report schemas are read-only for Phase 4 nodes.
- Offline rule and semantic fixtures are versioned, deterministic, and clearly
  labeled; real Provider/model checks require explicit opt-in and credentials.
- Every citation metric binds corpus, dataset, report, model, Prompt,
  configuration, and Git commit fingerprints; unknown values remain `null`/`n/a`.
- No credentials, production data, absolute paths, raw Provider responses, or
  unreviewed live content may enter fixtures, artifacts, events, or reports.
- No S2-S4 orchestration, production tracing, persistence/recovery, approval,
  budget governance, or broad web crawler is part of Phase 4.
- Reasonix nodes do not commit, tag, push, merge, release, or read/process
  `.reasonix/`; Codex accepts each node before the next starts.

## Frozen Phase 3 Interfaces

- Corpus loader and manifest: `app/research/corpus.py` and
  `data/phase3/sources/manifest.json`.
- Dataset loader and manifests: `app/evaluation/datasets.py` and
  `data/phase3/datasets/manifest.json`.
- Runner/report contracts: `app/evaluation/contracts.py`,
  `app/evaluation/runner.py`, `app/evaluation/reporting.py`.
- Report inputs are `manifest.json`, ordered `cases.jsonl`, `summary.md`, and
  optional `comparison.md`; Phase 4 adds citation output beside them and does
  not rewrite their meaning.

## Package Order And Dependencies

```text
P4-1 Citation Data Model + Fixtures
  -> P4-2 Deterministic Rule Support
     -> P4-3 Semantic Support Adapter
        -> P4-4 Citation Metrics + Evaluation Report
           -> P4-5 API + WebSocket Citation Delivery
              -> P4-6 React Citation Panel
                 -> P4-7 Integrated Acceptance + Handoff
```

---

## P4-1 — Citation Data Model And Versioned Fixtures

1. **Single goal.** Define validated claims, evidence spans, source levels,
   citation links, support judgments, and a versioned fixture that can be
   loaded from the frozen Phase 3 corpus without modifying it.
2. **Prerequisites.** Checkpoint `8afa4cd` and accepted Phase 3 contracts.
3. **Included / excluded.** Include schema validation, canonical serialization,
   source-span offsets, claim IDs, citation IDs, conflict/recency fields, and a
   small `seed-10-v1` citation fixture. Exclude support decisions, metrics,
   HTTP/WS wiring, frontend, and live fetching.
4. **Allowed modules.** Create `app/citations/__init__.py`,
   `app/citations/contracts.py`, `app/citations/fixtures.py`,
   `data/phase4/citations/manifest.json`,
   `data/phase4/citations/seed-10.jsonl`, and
   `tests/unit/phase4/test_citation_contracts.py`.
5. **Data contract.** `EvidenceItem` has `evidence_id`, `source_id`,
   `source_kind`, `source_version`, `title`, `locator` (line/offset range),
   `quote`, `content_sha256`, and `captured_at`. `Claim` has `claim_id`,
   `case_id`, `text`, `claim_type`, and ordered `citation_ids`. A
   `CitationRecord` links one claim to one evidence item and carries
   `rule_status`, `semantic_status`, `conflict_status`, `freshness_status`,
   and a `limitations` list. Status values are `supported`, `unsupported`,
   `conflict`, `stale`, or `unknown`; all IDs and hashes are strict.
6. **Safety / reproducibility invariants.** Fixture paths stay under
   `data/phase4/citations`; source IDs must resolve to the frozen corpus;
   quotes are bounded UTF-8 text; offsets and hashes are checked; unknown
   fields, duplicate IDs, traversal, absolute paths, and mismatched hashes
   fail closed.
7. **RED -> GREEN.** Add tests for valid round trips, duplicate IDs, invalid
   locators, source/hash mismatch, unsupported status, and traversal. Run
   `.venv/bin/python -m pytest tests/unit/phase4/test_citation_contracts.py -q`
   and require RED before implementing loaders and serializers, then rerun to
   GREEN.
8. **Minimum E2E evidence.** Load one seed case and prove every citation points
   to an existing frozen source span with a stable canonical hash.
9. **Definition of done.** The citation fixture is deterministic, validated,
   and consumable by later packages; Phase 2/3 code and data are unchanged.
10. **Bounded Reasonix node.** Whitelist exactly the files in item 4. Final
    report: changed files, RED, GREEN, static checks, unresolved risks;
    maximum 10 lines.

## P4-2 — Deterministic Rule Support Checks

1. **Single goal.** Implement offline lexical/structural checks that determine
   whether a claim is supported by its cited quote and source metadata.
2. **Prerequisites.** P4-1 accepted; citation contracts are frozen.
3. **Included / excluded.** Include exact quote containment, normalized token
   overlap, locator/hash validation, source-level policy, stale/conflict rules,
   and structured failure reasons. Exclude model entailment, metrics, API, and
   UI.
4. **Allowed modules.** Create `app/citations/rules.py` and
   `tests/unit/phase4/test_rule_support.py`; modify only
   `app/citations/contracts.py` if a validated result type is required.
5. **Data contract.** `RuleSupportChecker.check(claim, evidence) -> SupportJudgment`
   is pure and deterministic. It never upgrades `unknown`, `stale`, or
   `conflict` to `supported`; it returns a stable rule ID and redacted reason.
6. **Safety / reproducibility invariants.** No network or model call; no raw
   source outside the cited span; case/thread IDs cannot escape their scope;
   result ordering and reason codes are stable.
7. **RED -> GREEN.** Test exact support, token mismatch, malformed locator,
   stale source, conflicting evidence, and secret/path redaction; run the
   focused test file before and after the implementation.
8. **Minimum E2E evidence.** Evaluate the P4-1 fixture twice and prove byte-
   identical judgments and stable rule fingerprints.
9. **Definition of done.** Rule checks produce fail-closed judgments for every
   fixture citation and do not claim semantic entailment.
10. **Bounded Reasonix node.** Whitelist `app/citations/contracts.py`,
    `app/citations/rules.py`, and `tests/unit/phase4/test_rule_support.py`.

## P4-3 — Semantic Support Adapter

1. **Single goal.** Add a semantic support interface with a deterministic
   offline adapter and an explicitly opt-in real-model adapter.
2. **Prerequisites.** P4-2 accepted; rule judgments remain separate inputs.
3. **Included / excluded.** Include semantic result schema, mock entailment
   fixture, model/config fingerprints, timeout/error/skip handling, and
   separate real-smoke tests. Exclude automatic network use, citation metrics,
   API and frontend integration.
4. **Allowed modules.** Create `app/citations/semantic.py`,
   `tests/unit/phase4/test_semantic_support.py`, and
   `tests/integration/phase4/test_real_semantic_smoke.py`; modify only
   `app/settings.py` for opt-in flag parsing and `.env.example` for a
   non-secret flag description.
5. **Data contract.** `SemanticSupportChecker.check(claim, evidence, context) ->
   SemanticJudgment` returns `supported|unsupported|conflict|unknown|skipped`,
   `model_id`, `prompt_id`, `prompt_sha256`, `config_sha256`, and redacted
   limitation codes. Offline uses `mock:deterministic`; real mode runs only
   when `PHASE4_REAL_SEMANTIC_SMOKE=1` and credentials already exist.
6. **Safety / reproducibility invariants.** No credentials in prompts or
   reports; no real call when opt-in is absent; mock and real outputs are never
   aggregated together; unknown/timeout is not failure or support.
7. **RED -> GREEN.** Test deterministic mock decisions, opt-in skip, timeout,
   malformed model output, redaction, and fingerprint binding; run focused
   tests and the smoke file (expected skip without opt-in).
8. **Minimum E2E evidence.** The same claim/evidence pair yields identical
   offline judgment and fingerprint across two runs.
9. **Definition of done.** Semantic adapter is pluggable, fail-closed, and
   truthful about skipped or unknown real-provider evidence.
10. **Bounded Reasonix node.** Whitelist exactly the files in item 4 plus
    `app/citations/contracts.py` if needed; no provider credentials or network
    fixtures.

## P4-4 — Citation Metrics And Evaluation Reports

1. **Single goal.** Compute citation precision, recall, entailment, and
   unsupported-claim rate from rule and semantic judgments with honest unknown
   handling.
2. **Prerequisites.** P4-3 accepted; P4-1 fixture and Phase 3 report contracts
   remain read-only.
3. **Included / excluded.** Include metric definitions, per-case and aggregate
   rows, confidence/unknown counts, limitations, canonical metric fingerprints,
   and Markdown/JSON reports. Exclude API transport, frontend, S2-S4 and
   production observability.
4. **Allowed modules.** Create `app/citations/metrics.py`,
   `app/citations/reporting.py`, `scripts/evaluate_citations.py`,
   `tests/unit/phase4/test_citation_metrics.py`, and
   `tests/integration/phase4/test_citation_report.py`.
5. **Data contract.** `CitationMetrics` contains denominators and numerators
   for precision, recall, entailment and unsupported rate, plus `unknown_count`,
   `skipped_count`, `dataset_id/hash`, `corpus_id/hash`, `model_id`,
   `prompt_sha256`, `config_sha256`, and `git_commit`. Division by zero yields
   `null` and a limitation, never zero fabricated quality.
6. **Safety / reproducibility invariants.** Metrics consume only validated
   records; rule and semantic modes remain distinguishable; source and claim
   text are redacted from aggregate summaries unless explicitly bounded.
7. **RED -> GREEN.** Add failing denominator/duplicate/unknown/conflict tests,
   then run the focused unit/integration commands and compare two offline
   reports for stable rows and fingerprints.
8. **Minimum E2E evidence.** Run
   `.venv/bin/python scripts/evaluate_citations.py --dataset seed-10 --offline
   --output /tmp/phase4-citations-a` twice and compare canonical case rows,
   aggregates, and fingerprints.
9. **Definition of done.** Reports expose all four metrics, honest null/skip
   semantics, limitations, and complete provenance without claiming real model
   quality.
10. **Bounded Reasonix node.** Whitelist only the files in item 4 and the
    citation contract/result modules needed for integration.

## P4-5 — API And WebSocket Citation Delivery

1. **Single goal.** Attach validated citation results to a research task and
   expose them through additive HTTP and non-terminal WebSocket events.
2. **Prerequisites.** P4-4 report contract accepted; existing TaskRegistry and
   event bus contracts are frozen.
3. **Included / excluded.** Include additive schemas, task integration,
   citation artifact listing/download, and `citation_started` /
   `citation_completed` events. Exclude changing terminal ownership, replay,
   persistence, or replacing Phase 2 event version 1.
4. **Allowed modules.** Modify `app/api/schemas.py`, `app/api/events.py`,
   `app/api/tasks.py`, `app/api/server.py`, and the research runtime seam;
   create `tests/integration/phase4/test_citation_api.py` and
   `tests/integration/phase4/test_citation_events.py`.
5. **Data contract.** Add `GET /api/citations?thread_id=<uuid>` returning
   `{thread_id, claims, metrics, provenance}` and citation report files with
   relative names under the existing per-thread output root. Events retain
   version `1`, add only `citation_started` and `citation_completed` to the
   allowed type union, carry bounded IDs/statuses/fingerprints, and never carry
   secrets, absolute paths, raw Provider output, or full unbounded quotes.
6. **Safety / reproducibility invariants.** Thread isolation and path checks
   match Phase 2; one task still emits exactly one terminal event; citation
   failures become structured limitations and cannot turn a successful task
   into multiple terminal events; tutorial profile emits no citation events.
7. **RED -> GREEN.** Add failing API/WS tests for valid retrieval, foreign
   thread rejection, event ordering, event payload redaction, terminal count,
   and artifact download; run focused tests then the Phase 2 E2E.
8. **Minimum E2E evidence.** Start one agent-research task, observe citation
   events before the single terminal event, fetch claims/metrics for the same
   thread, and download the citation report.
9. **Definition of done.** Existing Phase 2 endpoints/events remain compatible;
   citation data is accessible only through validated thread-scoped paths.
10. **Bounded Reasonix node.** Whitelist only listed backend/API/tests files and
    the citation modules; do not alter frontend or frozen Phase 3 files.

## P4-6 — React Citation Panel

1. **Single goal.** Render claims, source snippets, support statuses, metrics,
   limitations, and citation report links in the existing workbench.
2. **Prerequisites.** P4-5 accepted API/event schemas; React Phase 2 tests
   remain the regression baseline.
3. **Included / excluded.** Include typed API/event parsing, additive state,
   chronological citation event display, claim-to-source panel, responsive
   layout, and safe text rendering. Exclude WYSIWYG editing, auth, persistence,
   arbitrary remote URLs, and new orchestration controls.
4. **Allowed modules.** Modify `frontend/src/workbench/types.ts`,
   `frontend/src/workbench/api.ts`, `frontend/src/workbench/useWorkbench.ts`,
   `frontend/src/App.tsx`, `frontend/src/app.css`, and
   `frontend/src/App.test.tsx`.
5. **Data contract.** Type the exact `GET /api/citations` response and the two
   citation event payloads; source links are server-returned relative artifact
   paths only; quotes render as text nodes; unsupported/unknown/skipped labels
   remain distinct.
6. **Safety / reproducibility invariants.** Reject unknown event versions/types,
   foreign thread IDs, unsafe paths, and malformed metrics; preserve the full
   chronological task/agent/tool/artifact/citation timeline; never use
   `innerHTML` or render raw Provider output.
7. **RED -> GREEN.** Add failing Vitest cases for parser rejection, event order,
   claim/source rendering, metric nulls, unsafe paths, and mobile layout class
   presence; run `pnpm --dir frontend exec vitest run` before and after the
   implementation, then ESLint/build.
8. **Minimum E2E evidence.** Browser smoke on 1440px and 375px shows citation
   statuses, source snippets, metrics, and report links without overlap while
   the existing event timeline remains complete.
9. **Definition of done.** The panel is additive, readable, secure, and does
   not regress tutorial task submission, event display, artifact preview, or
   downloads.
10. **Bounded Reasonix node.** Whitelist exactly the listed frontend files and
    no backend/data/credential files.

## P4-7 — Integrated Acceptance And Handoff

1. **Single goal.** Independently prove the complete Phase 4 citation flow and
   update canonical evidence for the next phase without claiming unrun real
   Provider quality.
2. **Prerequisites.** P4-1 through P4-6 independently accepted.
3. **Included / excluded.** Include fresh full gates, offline reproducibility,
   report hygiene scan, Phase 2/3 regression, and explicit real-smoke skips.
   Exclude tag/push/release and Phase 5 activation.
4. **Allowed modules.** Modify only `docs/phase-status.md`,
   `docs/verification/phase-4-evidence.md`, and
   `docs/phases/phase-4-trustworthy-citations.md`; create the evidence file
   if it does not exist. Implementation files are frozen after P4-6 acceptance.
5. **Evidence contract.** Record HEAD, branch, dirty flag, exact commands and
   exit codes, test counts, two-run fingerprints, all skipped reasons, metric
   definitions, browser dimensions, and unresolved limitations.
6. **Safety / reproducibility invariants.** Evidence distinguishes offline
   mocks from real providers; no secrets/absolute paths/raw responses; no
   status is marked accepted before Codex reruns the gates.
7. **RED -> GREEN.** Run the Phase 4 E2E, all Phase 4 tests, full backend,
   frontend Vitest/ESLint/build, Ruff, format, pre-commit and `git diff --check`.
   Any failure blocks acceptance and no release operation is allowed.
8. **Minimum E2E evidence.** One seeded agent-research task produces claims,
   citation events, metrics, Markdown/PDF citation artifacts, API retrieval,
   and browser rendering with exactly one terminal event.
9. **Definition of done.** Phase 4 evidence is independently reproducible,
   canonical status says accepted at `acf7c46`, and Phase 5 remains not started.
10. **Bounded Reasonix node.** This is a Codex-only acceptance/documentation
    node; do not launch Reasonix, modify implementation, commit, tag, push,
    release, or read/process `.reasonix/`.

## Review Checklist Before First Fresh Node

- Confirm the clean baseline is `8afa4cd84cdf3da4259b3570011c7d1d923fbd8e`.
- Confirm Phase 3 corpus, datasets, runner and report files are read-only.
- Confirm citation event additions preserve exactly one existing terminal event.
- Confirm offline semantic checks and real semantic smokes are separate.
- Confirm no package includes persistence, recovery, S2-S4, tracing, approval,
  budget governance, credentials or production content.
- P4-1 through P4-7 are accepted; any Phase 5 node requires a new explicit
  authorization and a new bounded plan.
