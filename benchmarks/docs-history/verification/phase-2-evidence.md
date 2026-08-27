# Phase 2 Verification Evidence

> **Final delegated acceptance — 2026-08-07 (HEAD `2d8698a`):** the user delegated Phase 2C
> independent acceptance to Codex. A fresh full rerun passed: E2E `1 passed`;
> integration/unit `355 passed, 9 skipped`; frontend `60 passed`; eslint/build,
> ruff/format, pre-commit (including Detect secrets), Compose config, offline
> doctor, and `git diff --check` all exited 0. Phase 2C is accepted. MySQL produced
> `6 skipped` because `PHASE2_MYSQL_INTEGRATION` was unset; the Docker client was
> installed but its daemon was inaccessible. Optional external Provider/model
> smokes produced `3 skipped` because their opt-in flags were unset; the required
> credentials were also absent. The existing release tag was not moved.

> **Current acceptance note — 2026-08-07 (B8 Integrated Safety Acceptance):**
> Phase 2A Demo Closure remains accepted at checkpoint `1d6166c`. Phase 2B
> Safety Hardening B1–B7 claims were re-verified by B8 fresh gates on the
> uncommitted working tree at HEAD `8dec2b7` (baseline `1d6166c`): backend E2E
> 1 passed; integration/unit 355 passed / 9 skipped (was 265/9 at 2A); frontend
> vitest 60 passed, eslint clean, build OK with bundle sizes identical to 2A
> (JS 155.92 kB / CSS 4.50 kB gzip); ruff check / ruff format / `git diff
> --check` clean. The Phase 2A browser evidence remains valid — B1–B7 changed
> no user-observable HTTP/WebSocket contract (see B8 section below). Only RED:
> `pre-commit run --all-files` detect-secrets hook requests a
> `.secrets.baseline` line-number refresh (B6 moved the fake-key entry in
> `tests/unit/phase2/test_external_adapters.py` from line 23 to 39; no new
> secrets) — outside B8's allowed files, reverted and listed as unresolved
> risk. Codex 于 2026-08-07 已独立重跑同一套门禁，结果一致；Phase 2B acceptance
> baseline 已刷新并提交，Phase 2B accepted；Phase 2C 正式启动。Existing tag
> `v0.1-tutorial-parity` points to `50680e6` and was not created or moved in this run.

> **Phase 2C C4 fresh mock quick start — 2026-08-07:** locked dependency sync
> completed. A local mock API run passed health, Markdown upload, task start
> (`202`), WebSocket observation (28 events; Web/Catalog/Knowledge tools; one
> `task_completed`), `/api/files`, and Markdown/PDF downloads (`200`; PDF starts
> `%PDF`). MySQL integration produced `6 skipped` because
> `PHASE2_MYSQL_INTEGRATION` was unset (Docker daemon access was also unavailable).
> Optional external Provider/model smokes produced `3 skipped` because their
> opt-in flags were unset; the required credentials were also absent.

> **Phase 2C runbook — 2026-08-07 (HEAD `fb17a39`):** the local mock
> reproduction and release verification runbook lives at
> [`docs/runbooks/phase-2-tutorial-parity.md`](../runbooks/phase-2-tutorial-parity.md)
> (README linked). All expected gate values in this file remain the source of
> truth; the runbook only re-states them. No gates were re-run on the Phase 2C
> working tree and no tag was created or moved in this node.

> **Phase 2C fresh gate run — 2026-08-07 (C2 node, HEAD `fb17a39` worktree):**
> all 11 release gates were re-run fresh on the Phase 2C working tree (C1 doc
> changes only — README, phase-status, phase doc, evidence, runbook; no product
> source/tests/dependencies touched) and every gate is GREEN. Results are
> byte-identical to the B8 table below: backend E2E 1 passed;
> integration/unit 355 passed / 9 skipped; frontend vitest 60 passed, eslint
> clean, build JS 155.92 kB / CSS 4.50 kB gzip; ruff check / ruff format (65
> files) / `docker compose config` / `doctor.py --offline` / `git diff --check`
> clean. The single B8 unresolved risk (detect-secrets `.secrets.baseline`
> line-number refresh) is resolved — `pre-commit run --all-files` passes 3/3
> with the baseline committed at `fb17a39`. No tag was created or moved.

## Fresh Gate Results — 2026-08-07 (Phase 2C C2, HEAD `fb17a39` worktree)

| Gate | Exit | Result |
|------|------|--------|
| `.venv/bin/python -m pytest tests/e2e/phase2/test_tutorial_closure.py -q` | 0 | 1 passed (upload → 202 start → three providers → exactly one `task_completed` → files/download); 1 `StarletteDeprecationWarning` (non-blocking) |
| `.venv/bin/python -m pytest tests/integration/phase2 tests/unit/phase2 -q` | 0 | 355 passed, 9 skipped |
| `pnpm --dir frontend exec vitest run` | 0 | 60 passed (1 file) |
| `pnpm --dir frontend exec eslint src` | 0 | clean |
| `pnpm --dir frontend run build` | 0 | `tsc -b && vite build` — JS 155.92 kB / CSS 4.50 kB gzip (byte-identical to 2A/2B evidence) |
| `.venv/bin/ruff check app tests` | 0 | clean |
| `.venv/bin/ruff format --check app tests` | 0 | 65 files already formatted |
| `.venv/bin/pre-commit run --all-files` | 0 | 3/3 hooks passed (ruff / ruff-format / Detect secrets) — B8 baseline-refresh RED resolved at `fb17a39` |
| `docker compose config` | 0 | valid (`mysql` service; host `3307` → container `3306`) |
| `.venv/bin/python scripts/doctor.py --offline` | 0 | Python 3.12.7 `[OK]`; "All offline checks passed." |
| `git diff --check` | 0 | clean |

**C2 notes:** no RED gates on the Phase 2C working tree. The gates modified no
files (`git status` before/after identical: only the four C1 docs modified).
Unchanged from B8: MySQL integration still skipped without
`PHASE2_MYSQL_INTEGRATION=1`; real-provider smokes (`test_real_model_smoke.py`,
`test_external_provider_smoke.py`) still skipped without credentials;
`StarletteDeprecationWarning` persists in backend runs (non-blocking). Tag
`v0.1-tutorial-parity` was not created or moved; creation waits for user
acceptance of Phase 2C.

## Fresh Gate Results — 2026-08-07 (B8 Integrated Acceptance, HEAD `8dec2b7` worktree)

| Gate | Exit | Result |
|------|------|--------|
| `.venv/bin/python -m pytest tests/e2e/phase2/test_tutorial_closure.py -q` | 0 | 1 passed (upload → 202 start → three providers → exactly one `task_completed` → files/download) |
| `.venv/bin/python -m pytest tests/integration/phase2 tests/unit/phase2 -q` | 0 | 355 passed, 9 skipped (B7 removed 124 duplicated/private-impl assertion lines; suite still grows from 265@2A) |
| `pnpm --dir frontend exec vitest run` | 0 | 60 passed (1 file) |
| `pnpm --dir frontend exec eslint src` | 0 | clean |
| `pnpm --dir frontend run build` | 0 | `tsc -b && vite build` — JS 155.92 kB / CSS 4.50 kB gzip (byte-identical to 2A evidence) |
| `.venv/bin/ruff check app tests` | 0 | clean |
| `.venv/bin/ruff format --check app tests` | 0 | 65 files already formatted |
| `.venv/bin/pre-commit run --all-files` | 0* | ruff / ruff-format passed; detect-secrets passed after the hook-updated `.secrets.baseline` was staged and committed (line 23→39; timestamp only, no new secrets) |
| `git diff --check` | 0 | clean |

**B1–B7 claim confirmation:** task lifecycle (B1/B2, exactly-one-terminal),
WebSocket disconnect/overflow/1013 (B3), HTTP negative contracts, thread
isolation and download containment (B4), parser/report atomic cleanup (B5),
Provider failure redaction and cleanup (B6), and test responsibility cleanup
(B7) are all covered by the 355-test suite above and pass.

**Phase 2A browser evidence validity:** B1–B7 changed backend-only behavior —
redacted error strings, stable `operation` values in `tool_completed` events
(`found N`/`done` → tool names, `app/tools/knowledge.py`), ai-only answer
collection (`app/agent/runtime.py`), xlsx parsing from binary file object
(`app/tools/files.py`). The frontend renders `event.type`/`tool_name` only and
never reads `operation`; E2E and the 60 frontend tests (unchanged) pass; the
production bundle is byte-identical to 2A. Event types, ordering, count,
terminal contract and artifact flow are unchanged → the 1440px/375px browser
smoke evidence remains valid; no browser rerun was required.

**Known limitations (B8):**
- `pre-commit run --all-files` is RED solely due to the detect-secrets
  `.secrets.baseline` line-number refresh; remediation: run the hook once and
  commit the updated baseline (1-line-number + timestamp change, no new
  secrets).
- Codex 于 2026-08-07 独立重跑所有 B8 门禁，结果与上表一致；Phase 2B formal
  acceptance completed after the baseline refresh.
- `StarletteDeprecationWarning` (httpx + starlette.testclient) appears in
  backend runs; non-blocking.
- Real-Provider smokes (`test_real_model_smoke.py`) remain skipped without
  `MODEL_API_KEY`; MySQL integration skipped without
  `PHASE2_MYSQL_INTEGRATION=1` — unchanged from 2A.

## Fresh Gate Results — 2026-08-06 (HEAD `198b0c7` + F1–F4 working tree)

### Frontend (F5, re-run this session)

| Gate | Exit | Result |
|------|------|--------|
| `pnpm --dir frontend exec vitest run` | 0 | 60 passed (1 file, no unhandled errors) |
| `pnpm --dir frontend exec eslint src` | 0 | clean |
| `pnpm --dir frontend run build` | 0 | `tsc -b && vite build` — dist generated (JS 155.92 kB / CSS 4.50 kB gzip) |

Coverage verified by the 60 tests (all 12.2 items): initial/reset state; successful upload; upload rejection; task start and duplicate/start failure; ordered Provider events with dedup and ascending sort; exactly-one-terminal client behavior; success/failure/cancellation; WebSocket disconnect and close `1013` slow-consumer message; Markdown plain-text preview and Markdown/PDF downloads built only from server-returned relative paths; stale success clearing on new/failed/cancelled runs and new sessions. Safety checks in `frontend/src`: no `dangerouslySetInnerHTML`, no browser storage of keys, `downloadUrl` rejects absolute paths/separators/traversal, `parseEvent` rejects malformed JSON/unknown versions/types with stable user-safe messages, `requestJson` never leaks raw response text.

### Backend regression (re-run this session)

| Gate | Exit | Result |
|------|------|--------|
| `pytest tests/e2e/phase2/test_tutorial_closure.py -q` | 0 | 1 passed |
| `pytest tests/integration/phase2 tests/unit/phase2 -q` | 0 | 265 passed, 9 skipped |
| `ruff check app tests` | 0 | clean |
| `ruff format --check app tests` | 0 | 65 files already formatted |
| `pre-commit run --all-files` | 0 | ruff / ruff-format / Detect secrets passed |
| `git diff --check` | 0 | clean |

Observed in the E2E closure run (TestClient, in-process): upload → 200, task start → 202, `internet_search`, `list_sql_tables`, `list_knowledge_assistants` all present, exactly one terminal event (`task_completed`), `/api/files` lists both reports, `/api/download` returns both (PDF begins `%PDF`), downloaded Markdown contains `UNIQUE-E2E-CONSTRAINT-20260801` and all three provider modes. The integration/unit gate separately proves cross-thread isolation, relative artifact paths, and that terminal/report-error data does not expose secrets or absolute paths.

### Browser smoke (1440px / 375px) — PASSED

The local mock backend and Vite frontend were started at `127.0.0.1:8000` and `127.0.0.1:5173`. A temporary 58-byte Markdown constraint containing `UNIQUE-BROWSER-SMOKE-20260806` was uploaded through the real browser UI.

| Viewport | Result |
|------|------|
| 1440 × 1000 | mock health and WebSocket open; upload accepted; 28 ordered events; `internet_search`, `list_sql_tables`, `list_knowledge_assistants`; one `task_completed`; two artifact events; Markdown preview contained the unique marker; Markdown and PDF download events received; `scrollWidth == clientWidth == 1440` |
| 375 × 812 | new UUID/session; upload and task repeated; 28 ordered events; all three Provider families; one terminal; Markdown marker present; `scrollWidth == clientWidth == 375` |

Download anchors used the active UUID and server-returned `tutorial-report.md` / `tutorial-report.pdf` relative paths under `/api/download`. The browser rendered all task, agent, tool, artifact and terminal events without collapsing or dropping entries.

## Historical Evidence (Chronological)

## Environment
- **OS:** darwin/arm64 **Date:** 2026-07-29
- **Python:** 3.12, **Pydantic:** 2.13.4

## Event Type Design

```python
# PEP 695 recursive type alias
type JsonValue = (
    None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
)

class TutorialEvent(BaseModel):
    data: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("data", mode="before")
    @classmethod
    def _validate_data(cls, value):
        _validate_json_value_strict(value)  # rejects before Pydantic coercion
        return value
```

**Strict behavior:**
- `bytes`, `bytearray`, `set`, `frozenset`, `tuple`, `object()`, non-string dict keys → **REJECTED** (ValidationError)
- Field-level `mode="before"` validator prevents Pydantic default coercion
- JSON Schema contains `$defs/JsonValue` with recursive references
- `data.additionalProperties.$ref` → `#/$defs/JsonValue`

## Final Gate

| Gate | Exit | Result |
|------|------|--------|
| `pytest tests/ -q` | 0 | 187 passed, 10 skipped |
| `ruff check` | 0 | clean |
| `ruff format --check` | 0 | all formatted |
| `pre-commit run --all-files` | 0 | 3/3 passed |
| `docker compose config` | 0 | valid |
| `git diff --check` | 0 | clean |
| MySQL integration (`PHASE2_MYSQL_INTEGRATION=1`) | 0 | 6 passed |

## Direct Rejection Evidence
```
bytes     → REJECTED (ValidationError)
set       → REJECTED (ValidationError)
tuple     → REJECTED (ValidationError)
object    → REJECTED (ValidationError)
non-str key → REJECTED (ValidationError)
```

## Known Limitations
- `b"x"` inside a dict key → rejected at field_validator level
- `.secrets.baseline` unchanged
## Task 3 remediation status: remediated (n4/n5/n6) — awaiting acceptance

### Independent rejection reproduction (2026-07-29)
```
outside before = 'SAFE'
fixed_tmp exists = True
fixed_tmp.is_symlink() = True
fixed_tmp.resolve() = <path outside workspace>
outside after = 'OVERWRITTEN'
result_is_symlink = True
result_resolves_outside = True
```
Fixed `.name.tmp` symlink in workspace allows overwriting arbitrary files outside the workspace boundary.

## Task 4: Agent Factory & Runtimes — REJECTED
- factory missing `workspace_factory` parameter
- mock runtime `_emit_tool_pair` fires both events before provider call
- real runtime stream normalizer duplicates wrapper tool events
- agent_started/agent_completed missing `agent_name` in data
- real-model smoke reads MODEL_API_KEY but doesn't use it

All remediation commits applied. Acceptance base: bc41e3c. 322 passed, 11 skipped.

## Task 3: Workspace & Reports Remediation

**Date:** 2026-07-29

### RED Phase (87a4373)
- 4 test files rewritten: 91 total tests
- 42 RED failures covering: UnsafeWorkspacePath rejection (no silent basename), nested traversal, pypdf/docx/openpyxl real parsing, macro/ZIP bomb defense, untrusted source delimiters, report contracts
- Representative failures:
  - `test_rejects_parent_traversal_single` → ValueError → UnsafeWorkspacePath
  - `test_rejects_directory_component` → basename sanitization rejected
  - `test_pdf_extracts_text_not_placeholder` → real pypdf text required
  - `test_rejects_macro_enabled_docx` → vbaProject.bin rejection
  - `test_rejects_zip_bomb` → entry/size/ratio checks
  - `test_untrusted_delimiters_warn_about_instructions` → BEGIN/END markers
  - `test_uses_current_session_workspace` → session-based output_dir

### GREEN Phase (e74c64a)
- `app/tools/files.py`: UnsafeWorkspacePath, is_relative_to containment, read_uploaded_file with untrusted delimiters, pypdf PdfReader, python-docx with macro content-type/entry/ZIP bomb checks, openpyxl read_only/data_only with sheet info
- `app/tools/reports.py`: session_context-based output_dir, atomic Markdown/PDF, STSong-Light CJK font, ReportGenerationError without raw paths
- `app/agent/factory.py` + `runtime.py`: updated report call signatures

```bash
.venv/bin/python -m pytest tests/unit/phase2/test_workspace.py \
  tests/unit/phase2/test_context.py \
  tests/unit/phase2/test_file_reader.py \
  tests/unit/phase2/test_reports.py -q
# 91 passed

.venv/bin/python -m pytest tests/ -q
# 302 passed, 11 skipped

.venv/bin/ruff check app tests
# All checks passed

.venv/bin/ruff format --check app tests
# All files already formatted

.venv/bin/pre-commit run --all-files
# ruff, ruff-format, detect-secrets all passed
```

### Security evidence
- Path traversal: 13 negative tests (../, absolute, Windows, backslash, symlink, directory component) → all UnsafeWorkspacePath
- Macro rejection: vbaProject.bin entry + macro content type → rejected
- ZIP bomb: excessive entries, compression ratio, uncompressed size → rejected
- MIME spoofing: .pdf extension + text content → rejected by PDF header check
- Untrusted delimiters: [BEGIN UNTRUSTED]...[END UNTRUSTED] with instruction warning
- Atomaticity: tmp file clean; failed upload preserves old file; failed PDF preserves Markdown
- Error redaction: ReportGenerationError without paths; current_session error without paths/credentials

### Artifact return example
```python
generate_markdown_report("# Report\n\nContent.")
# Returns: "tutorial-report.md"  (relative path, not absolute)
```

### Remaining blockers
- None for Task 3
- Task 4 already completed (c5b579e) — unaffected by remediation
- Historical snapshot: Task 5 not yet started

## Task 4: Agent Factory & Runtimes

**Date:** 2026-07-29

### RED Phase
- Wrote 4 test files (24 tests total) all failing on import — modules did not exist.

### Implementation
- `app/agent/factory.py`: `create_tutorial_agent(model, bundle, events)` — assembles DeepAgents graph:
  - Creates web/catalog/knowledge tool sets from ProviderBundle
  - Builds 3 subagents via `build_tutorial_subagents`
  - Creates main-level tools: `read_uploaded_file`, `generate_markdown_report_tool`, `generate_pdf_report_tool`
  - Calls `create_deep_agent()` with: injected model, MAIN_PROMPT, main tools, subagents, InMemorySaver, name "tutorial-research-agent"
  - All tools use `RunnableConfig.configurable.thread_id` for event routing

- `app/agent/runtime.py`: Value objects + two runtimes behind TutorialRuntime protocol:
  - `RuntimeRequest(query, context)` / `RuntimeResult(answer, artifacts)` frozen dataclasses
  - `TutorialRuntime` Protocol: `async def run(request) -> RuntimeResult`
  - `MockTutorialRuntime(bundle, events)`: Deterministic fixed sequence through all 3 providers, reads uploaded .md fixtures, generates both reports, emits paired agent/tool + artifact events, NEVER emits task lifecycle/terminal events
  - `DeepAgentsTutorialRuntime(graph, bundle, events)`: Real `agent.astream()` with stream_mode="updates", normalizes agent/tool events from stream chunks, generates reports, resets session_context

### GREEN Phase
```bash
.venv/bin/python -m pytest tests/unit/phase2/test_agent_factory.py \
  tests/unit/phase2/test_runtime_events.py \
  tests/integration/phase2/test_mock_runtime.py -q
# 24 passed

.venv/bin/python -m pytest tests/integration/phase2/test_real_model_smoke.py -q
# 1 skipped (no MODEL_API_KEY — correct skip behavior)

.venv/bin/ruff check app/agent tests/unit/phase2 tests/integration/phase2
# All checks passed

.venv/bin/ruff format --check app/agent tests/unit/phase2 tests/integration/phase2
# 26 files already formatted

.venv/bin/python -m pytest tests/ -q
# 238 passed, 11 skipped
```
