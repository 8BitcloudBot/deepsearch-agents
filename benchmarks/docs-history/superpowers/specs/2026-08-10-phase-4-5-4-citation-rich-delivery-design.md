# P4.5-4 Citation-Rich Delivery Design

**Status:** Approved design, pending implementation plan

**Goal:** Deliver the validated live source and evidence records produced by
P4.5-3 through thread-scoped JSON, Markdown, PDF, artifact downloads, and
non-terminal WebSocket progress without changing the frozen Phase 4 citation
endpoint or tutorial/offline behavior.

## Scope and Invariants

P4.5-4 is a backend delivery package. It does not modify the React workspace,
real-provider smoke, orchestration strategies, persistence, or production
observability. No network, model, provider, or data source is used by tests.

The existing `GET /api/citations` endpoint remains unchanged and continues to
serve the Phase 4 evaluation report. Live provenance is exposed by a new
thread-scoped endpoint. Existing `/api/files` and `/api/download` behavior is
reused for showcase artifacts. `TaskRegistry` remains the sole owner of task
terminal events.

All serialized live values are bounded and redacted. Source records must pass
`SourceLocator.as_live_source_result()`. Evidence and limitations are copied
from the request-local `LiveSourceCollector`; raw provider responses,
credentials, absolute paths, queries, and untrusted exception text never enter
JSON, reports, or event data.

## Architecture

`ShowcaseResearchRuntime` receives an optional `ShowcaseCitationDelivery`
implementation. The runtime keeps ownership of `session_context` and the
collector context. After the executor returns (including a degraded result),
the delivery writes a canonical live citation document and the two showcase
reports. P4.5-3 callers that do not inject delivery retain their current
behavior and empty artifacts.

The delivery component has one responsibility: convert a validated
`ShowcaseRunResult` into stable, thread-scoped artifacts and progress events.
It does not call providers or resolve locators.

## Live Citation Document

Each successful or degraded showcase task writes `live-citations.json` under
the request workspace output directory. Its JSON-safe shape is:

```json
{
  "schema_version": "1.0.0",
  "thread_id": "<uuid>",
  "answer": "<redacted answer>",
  "claims": [
    {
      "claim_id": "claim-1",
      "statement": "<one non-empty answer paragraph>",
      "evidence_ids": ["ev-live-..."]
    }
  ],
  "sources": [
    {
      "type": "live_source_result",
      "source_id": "src-...",
      "source_kind": "web|mysql|knowledge|uploaded-file",
      "title": "<bounded title>",
      "captured_at": "<timezone-aware timestamp>",
      "version": "<semantic adapter version>",
      "display_text": "<bounded text>",
      "locator": {"kind": "url|row|chunk|span", "value": "<safe value>"},
      "execution_mode": "live",
      "evidence_partition": "live"
    }
  ],
  "evidence": [
    {
      "evidence_id": "ev-live-...",
      "source_id": "src-...",
      "source_kind": "web|mysql|knowledge|uploaded-file",
      "locator": {"kind": "...", "value": "..."},
      "quote": "<redacted bounded quote>",
      "content_sha256": "<sha256>",
      "thread_id": "<uuid or null>"
    }
  ],
  "limitations": [
    {"code": "...", "source_kind": "...", "message": "<redacted>"}
  ],
  "artifacts": ["live-citations.json", "showcase-report.md", "showcase-report.pdf"]
}
```

Claims are deterministic delivery claims, not new model assertions. Split the
redacted answer on blank-line boundaries, discard empty segments, and assign
`claim-1`, `claim-2`, and so on in first-seen order. Every claim references all
evidence IDs from that run. When no evidence exists, `evidence_ids` is empty and
the limitations section communicates the missing or unavailable sources.

Source records are generated with `as_live_source_result()` using the request
thread for uploaded files. Evidence records use `LiveEvidence.as_dict()`.
The document is written canonically with sorted keys and a trailing newline.

## Markdown and PDF Reports

Both reports derive from the same canonical delivery model. The Markdown report
contains:

1. A title and the redacted answer paragraphs, each labeled with its claim ID.
2. A `Claims and Evidence` section listing statement and evidence IDs.
3. An `Evidence` section listing quote, source ID, and locator.
4. A `Sources` section listing title, source kind, capture time, adapter version,
   locator, and only an approved Web/upload display link when present.
5. A `Limitations` section when limitations are present.

The PDF uses the existing report generator with an additive safe basename
parameter. Defaults remain `tutorial-report.md` and `tutorial-report.pdf`; the
showcase uses `showcase-report.md` and `showcase-report.pdf`. No absolute output
path or user-supplied filename is accepted.

## API and WebSocket Delivery

Add `GET /api/live-citations?thread_id=<uuid>` and a response model containing
the validated JSON document plus the requested thread ID. Validate the UUID,
resolve the output filename through `SessionWorkspace.resolve_output()`, return
404 when the document is absent, and never expose filesystem paths in errors.
The existing `/api/citations` route, response model, and report lookup remain
unchanged.

Within the showcase runtime, delivery emits these non-terminal events in order:

```text
citation_started
artifact_created (live-citations.json)
artifact_created (showcase-report.md)
artifact_created (showcase-report.pdf)
citation_completed
```

Event data contains only counts, relative artifact names, media types, and a
`status` of `completed` or `degraded`. A delivery exception adds one generic
`delivery-failed` limitation, emits a degraded `citation_completed` event, and
does not leak the exception. The runtime then returns normally so the task
registry emits exactly one `task_completed` event, consistent with P4.5-3's
degraded-completion semantics.

## Failure Behavior

- Missing evidence does not create fabricated citations or empty source links.
- Invalid/stale locators remain absent from the source/evidence arrays and their
  existing limitations are rendered verbatim only after redaction.
- A missing output document yields HTTP 404; malformed or foreign thread input
  yields HTTP 400.
- Markdown/PDF/JSON write failure produces no partial artifact, records a generic
  delivery limitation, and preserves the answer and collected evidence in the
  in-memory result.
- Tutorial, agent-research, existing Phase 4 API, reports, and event behavior are
  unchanged when no showcase delivery is injected.

## Test Responsibility and Acceptance

Unit tests own canonical claim generation, JSON serialization, redaction,
Markdown rendering, safe links, limitation rendering, and report writer
filename compatibility. Integration tests own the showcase runtime-to-delivery
event sequence, artifact creation, live citation API retrieval, download
behavior, missing-document 404, and one terminal task event. Existing Phase 2,
Phase 3, Phase 4 citation, and P4.5-1 through P4.5-3 focused regressions remain
the compatibility gate.

Minimum package commands:

```bash
PYTHONPATH=. UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run pytest \
  tests/unit/phase4_5 tests/integration/phase4_5 \
  tests/unit/phase2/test_reports.py tests/unit/phase2/test_runtime_events.py \
  tests/unit/phase2/test_api.py tests/unit/phase2/test_websocket.py \
  tests/unit/phase3/test_research_profile.py \
  tests/integration/phase3/test_research_runtime.py \
  tests/unit/phase4/test_citation_contracts.py -q

UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run ruff check \
  app/showcase app/api app/main.py app/tools/reports.py \
  tests/unit/phase4_5 tests/integration/phase4_5

UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run ruff format --check \
  app/showcase app/api app/main.py app/tools/reports.py \
  tests/unit/phase4_5 tests/integration/phase4_5

git diff --check
```
