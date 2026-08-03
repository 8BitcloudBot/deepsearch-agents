# Phase 2 Verification Evidence

> **Current acceptance note — 2026-08-01:** Phase 2 is in progress at
> Phase 2A Demo Closure. HEAD `397ae23` contains Task 5 remediation, but the
> latest independent focused E2E check still failed because no Knowledge
> Provider tool event was observed. Phase 2 is not accepted, Task 6/React has
> not started, and no `v0.1*` tag exists. Older rejection labels, commit bases,
> test totals and “remaining blockers” below are chronological evidence, not
> the current status. See [`../phase-status.md`](../phase-status.md).

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
