# Phase 10 S3-6 Live Acceptance Evidence

**Date:** 2026-08-14

**Result:** Not accepted. The separately authorized isolated source smokes
passed, but the combined browser journey entered repeated tool calls and ended
with one safe terminal failure. No result or report artifacts were delivered.

## Authorization and Boundary

The user authorized one bounded S3-6 real acceptance covering an
OpenAI-compatible model, Tavily, a non-production read-only MySQL instance,
local knowledge retrieval, and one combined browser run. The authorization did
not include commit, push, release, publication, deployment, production data, or
production-readiness claims.

Credentials remained server-side. This record excludes credential values and
locations, raw Provider responses, and raw exception text. The worktree was on
`main`, one commit ahead of the locally known `origin/main`, with pre-existing
Phase 10 changes preserved.

## Isolated Smokes

| Capability | Result | Bounded observation |
|---|---|---|
| OpenAI-compatible model | Passed | One minimal request returned non-empty model output; only safe metadata was inspected. |
| Tavily Web search | Passed | One bounded query requested at most one result and returned a valid URL locator. |
| MySQL | Passed | A non-production, read-only allowlisted query returned three bounded `drugs` rows. |
| Local knowledge | Passed with qualification | One existing fixture document was embedded with FastEmbed, indexed in Qdrant Local, and retrieved with a chunk locator. |

The formal six-document knowledge bodies and built index were absent from this
workspace. The local knowledge smoke therefore proves adapter execution and
locator shape only; it is not formal-corpus acceptance and does not establish
retrieval quality.

The live `/health` response described all five capabilities as ready and did
not expose Profile or Runtime fields. Readiness is descriptive and does not
prove a successful research journey.

## Web Evidence Boundary Corrections

The live run exposed three normalization defects at the Web evidence boundary:
oversized raw page content was preferred over the bounded summary, title and
summary lengths were not bounded before evidence validation, and one invalid
hit could fail the whole result set. The adapter now uses bounded summary
content, caps titles at 200 characters and summaries at 2,048 characters, and
isolates invalid hits while retaining later valid evidence. A zero-valid-hit
result returns an explicit `no-evidence` limitation.

Focused regression command:

```bash
.venv/bin/pytest -q tests/unit/phase2/test_external_adapters.py tests/unit/research/test_tools.py
```

The focused boundary tests passed: `15 passed`.

## Combined Browser Run

The final authorized journey requested uploaded-file, Web, read-only MySQL,
and local-knowledge evidence in one research task.

- Thread: `1f4bb873-6144-4a84-a86d-949cb2747d8c`
- Task/planning/collection events: `1 / 1 / 1`
- Uploaded-file started/completed: `1 / 1`
- Local-knowledge started/completed: `15 / 12`
- Web started/completed: `27 / 27`
- MySQL started/completed: `6 / 3`
- Terminal failure events: `1`
- JSON/Markdown/PDF artifacts: `0 / 0 / 0`

The visible terminal message was:

> 研究任务失败，请检查研究模型和可用数据源后重试

The repeated calls indicate a missing bounded stop condition or tool budget in
the combined graph. The exact exception class was not captured, so this record
does not classify it as a specific framework exception. The next package must
add explicit per-run/per-tool budgets, stop conditions, and a safe terminal
classification before another combined live acceptance attempt.

## Responsive Failure-State QA

The preserved failed result page was inspected at desktop `1440x900` and
mobile `375x812`. Both viewports showed the safe failure alert and the same
thread identity. At both sizes, document and body scroll width equaled the
viewport width, so no horizontal overflow was present. This verifies only the
responsive failure state; successful desktop/mobile browser acceptance remains
open.

## Acceptance Decision

S3-6 remains incomplete. Isolated connectivity and adapter boundaries passed
within the authorized scope, but the combined research success path, canonical
result, citations, and exact JSON/Markdown/PDF delivery were not produced. No
claim is made about quality, accuracy, latency, cost, SLA, production
readiness, release, publication, or deployment.
