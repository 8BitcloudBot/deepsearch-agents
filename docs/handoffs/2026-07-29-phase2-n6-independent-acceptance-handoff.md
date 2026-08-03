# Phase 2 Handoff - N6 Independent Acceptance

**Created:** 2026-07-29
**Repository:** `deepsearch-agents`
**Branch / HEAD:** `main` / `2241ef2ec8f9991f6cdbb8a589e28bc750948b5d`
**Status:** DeepSeek reports N6 complete; independent acceptance has not been run.

## Continuation Goal

Independently accept or reject the Phase 2-n6 remediation for Tasks 3-4. Do
not start Phase 2 Task 5, create a `v0.1*` tag, or edit implementation code
while performing this review. If N6 is accepted, explicitly authorize Task 5
planning/implementation only after reporting the evidence to the user.

## Current State

- Tasks 0-2 were accepted earlier. Task 3-4 were repeatedly rejected during
  independent review, most recently at N5.
- DeepSeek subsequently committed `2241ef2`:
  `fix: enforce wrapper failure contract and fix artifact dedup`.
- The working tree was clean when this handoff was created; no `v0.1*` tag
  existed.
- The live status file says `awaiting_independent_acceptance`, but several
  older fields in `docs/phase-status.md` and the N4 handoff remain stale. Do
  not rely on either as evidence of acceptance.

## What N6 Claims To Fix

- The `read_uploaded_file` LangChain wrapper no longer emits
  `tool_completed` after a reader exception.
- `DeepAgentsTutorialRuntime` now recognizes the actual main-level report
  tool names, `generate_markdown_report_tool` and
  `generate_pdf_report_tool`, before deciding whether compensation is needed.
- `tests/unit/phase2/test_runtime_events.py` adds failure, exact-pair, and
  agent payload tests.

These claims are unverified. In particular, confirm that N6 has tests for the
**factory wrapper** failure path, not only the mock runtime, and that a stream
containing real report-tool messages causes no second report creation and no
duplicate `artifact_created` event.

## Key Artifacts

- Authoritative Phase 2 plan:
  `docs/superpowers/plans/2026-07-29-agent-engineering-research-copilot-phase-2-plan.md`
- Remediation contract and acceptance checklist:
  `docs/superpowers/plans/Phase 2-n4.md`
- Locked decisions: `docs/adr/0003-phase-2-tutorial-contracts.md`
- Historical evidence: `docs/verification/phase-2-evidence.md`
- Current status (partly stale; inspect critically): `docs/phase-status.md`
- Previous stale handoff: `docs/handoffs/2026-07-29-phase2-task4-handoff.md`
- N6 diff: `git diff 51d2b89...2241ef2`
- Main review targets:
  `app/agent/factory.py`, `app/agent/runtime.py`,
  `tests/unit/phase2/test_runtime_events.py`

## Durable Constraints

- `TaskRegistry` alone owns `task_started` and all terminal task events.
- Tool wrappers own tool events. On a failed call, the exception propagates
  and no successful `tool_completed` event may be emitted.
- `agent_started` and `agent_completed` carry `agent_name`.
- Artifacts exposed outside the workspace use relative paths only. Report
  wrapper creation and runtime compensation must produce each artifact/event
  exactly once per run.
- Uploaded data enters runtimes only through `read_uploaded_file` and remains
  untrusted source material.
- Do not regenerate `.secrets.baseline`.

## Prior Verified Evidence

The N5 review independently established:

- `save_uploaded_file()` now rejects malformed PDF, DOCX, XLSX, and non-UTF-8
  text by final target extension.
- `_write_all()` closes the previous short-write gap.
- PDF table cells now use CJK-capable ReportLab Paragraphs.
- At N5, the factory wrapper emitted `tool_started` then `tool_completed` on
  a reader failure, and runtime artifact tracking used the wrong report-tool
  names; those were valid blockers.
- N5 gates passed: `314 passed, 11 skipped`, ruff, ruff-format,
  pre-commit, `docker compose config`, and `git diff --check`.

Do not assume this evidence covers N6. Rerun the relevant checks on the
current HEAD.

## Verification To Run

1. Inspect `git status --short --branch`, `git log --oneline 51d2b89..HEAD`,
   and `git diff --check 51d2b89...HEAD`.
2. Reproduce factory wrapper failure by subscribing to `InMemoryEventBus`,
   invoking `_build_read_uploaded_file_tool` with no active session / a failing
   reader, and assert the event sequence is only `tool_started`.
3. Feed `DeepAgentsTutorialRuntime` a fake graph stream containing tool
   messages named `generate_markdown_report_tool` and
   `generate_pdf_report_tool`; patch report writers and assert neither
   compensation writer is called and no duplicate artifact is emitted.
4. Confirm `workspace_factory` still matches the exact locked interface and
   that its reserved role is documented rather than silently creating another
   session/workspace source.
5. Run:

   ```bash
   .venv/bin/python -m pytest tests/unit/phase2/test_context.py tests/unit/phase2/test_workspace.py tests/unit/phase2/test_file_reader.py tests/unit/phase2/test_reports.py tests/unit/phase2/test_agent_factory.py tests/unit/phase2/test_runtime_events.py tests/integration/phase2/test_mock_runtime.py tests/integration/phase2/test_real_model_smoke.py -q
   .venv/bin/python -m pytest tests/ -q
   .venv/bin/ruff check app tests docker
   .venv/bin/ruff format --check app tests
   .venv/bin/pre-commit run --all-files
   docker compose config
   git diff --check
   git status --short
   git tag --list 'v0.1*'
   ```

## Decision Rule

- Reject N6 and keep Task 5 blocked if any event ordering/ownership,
  report-artifact de-duplication, documentation-truthfulness, or gate failure
  remains. Give the user a concise paste-ready DeepSeek remediation prompt.
- Accept Tasks 3-4 only with fresh command output and direct behavior evidence.
  Then state that Task 5 is authorized, but do not begin Task 5 unless the
  user asks.

## Suggested Skills

- `using-superpowers`: mandatory session-start skill discovery.
- `two-axis-review`: separate repository-quality findings from Phase 2 plan
  compliance.
- `verification-before-completion`: required before declaring acceptance.
- `handoff`: use again if the next session must transfer the result onward.
