# P4.5-5 React Showcase Polish Design

**Status:** Approved design, pending written-spec review

**Goal:** Turn the existing React research console into a profile-aware,
claim-first showcase that presents P4.5 live claims, evidence, sources,
limitations, progress, and reports without changing tutorial, Phase 4
evaluation, API, or WebSocket contracts.

## Scope And Invariants

P4.5-5 is a frontend-focused package with one bounded backend closure: the
already-frozen uploaded-file `safe_display_link` must resolve through the
server. It does not call a real model or Provider, add a new event type, change
the Phase 4 `/api/citations` response, redesign the evaluation runner, or begin
P4.5-6 live smoke work.

The three application profiles remain semantically separate:

- `showcase` reads the P4.5 `/api/live-citations` document and showcase report
  artifacts.
- `agent-research` retains the Phase 4 `/api/citations` evaluation panel and
  citation artifact behavior.
- `tutorial` retains the accepted tutorial upload, task, event, and report
  behavior.

`GET /health` already returns `app_profile`; the frontend adds this field to
its validated `HealthInfo` contract and uses it as the only profile-routing
signal. It does not probe both citation endpoints or infer profile from a 404.

## Architecture

The existing workbench hook remains the owner of session, run, WebSocket,
artifact, and asynchronous-response guards. P4.5-5 adds a parallel live
citation state owned by that hook and a focused `ShowcaseResults` component for
rendering it. The existing Phase 4 citation parser, state, and panel remain in
place for `agent-research`.

The data flow is:

```text
GET /health
  -> app_profile
  -> profile-specific event interpretation
  -> showcase citation_completed(completed)
  -> GET /api/live-citations?thread_id=<current UUID>
  -> strict frontend parser
  -> claim-first ShowcaseResults
```

The workbench accepts only responses whose `thread_id` equals the active
session. Existing `sessionRef` and `runRef` guards reject late results after a
new run or new session.

## Frontend Contracts

Add typed live delivery records matching the P4.5-4 document:

```ts
type LiveSourceKind = "web" | "mysql" | "knowledge" | "uploaded-file";

interface LiveLocator {
  kind: "url" | "row" | "chunk" | "span";
  value: string;
}

interface LiveCitationClaim {
  claim_id: string;
  statement: string;
  evidence_ids: string[];
}

interface LiveEvidence {
  evidence_id: string;
  source_id: string;
  source_kind: LiveSourceKind;
  locator: LiveLocator;
  quote: string;
  content_sha256: string;
  thread_id: string | null;
}

interface LiveSource {
  type: "live_source_result";
  source_id: string;
  source_kind: LiveSourceKind;
  title: string;
  captured_at: string;
  version: string;
  display_text: string;
  locator: LiveLocator;
  execution_mode: "live";
  evidence_partition: "live";
  safe_display_link?: string;
}

interface LiveLimitation {
  code: string;
  source_kind: LiveSourceKind | null;
  message: string;
}

interface LiveCitationDocument {
  schema_version: "1.0.0";
  thread_id: string;
  answer: string;
  claims: LiveCitationClaim[];
  sources: LiveSource[];
  evidence: LiveEvidence[];
  limitations: LiveLimitation[];
  artifacts: [
    "live-citations.json",
    "showcase-report.md",
    "showcase-report.pdf",
  ];
}
```

`parseLiveCitationDocument(value, expectedThreadId)` fails closed. It requires
the exact schema version and artifact names, current thread ownership,
sequential claim IDs, unique evidence/source IDs, known source/locator pairs,
and claim references that resolve to existing evidence. A structural contract
failure rejects the entire document so malformed claims, evidence, or source
records never reach render state. Display-link validation is field-local: an
otherwise valid source remains visible, but an invalid link is omitted.

Safe link parsing is source-specific:

- Web links must be HTTP/HTTPS and equal the validated URL locator value.
- Uploaded-file links must equal
  `/api/threads/<current-thread>/uploads/<encoded-basename>`.
- MySQL and knowledge records must not contain a display link.
- A link that fails these checks is omitted without deriving a replacement
  from raw locator text.

## Event And State Behavior

The two existing `citation_completed` payloads remain distinct:

- Phase 4 evaluation: `completed|failed`, partition count, fingerprint, and
  string limitations.
- P4.5 showcase delivery: `completed|degraded`.

When `app_profile` is `showcase`, `citation_started` supplies claim/evidence
progress counts when the payload is valid. A `citation_completed` event with
`status: "completed"` loads `/api/live-citations`. A degraded completion does
not probe a document that delivery failed to publish; it exposes a stable
delivery-unavailable state and still allows the terminal task status to become
successful under the existing TaskRegistry contract.

Live state includes document, loading, safe error, delivery status, and
optional citation progress counts. A new run and new session clear all live
state. Foreign-thread events remain ignored. Event timeline rendering remains
plain text and preserves every accepted event.

Artifact refresh recognizes profile-specific reports:

- `showcase-report.md` and `showcase-report.pdf` for showcase;
- `tutorial-report.md` and `tutorial-report.pdf` for tutorial;
- existing Phase 4 citation artifacts for agent-research.

Markdown previews continue to use text nodes only. Downloads continue to use
server-returned safe basenames through `/api/download`.

## Uploaded-Source Route

Add the route frozen by the P4.5-2 locator contract:

```text
GET /api/threads/{thread_id}/uploads/{name}
```

The server validates the UUID, resolves `name` only through
`SessionWorkspace.resolve_upload()`, and returns only an existing regular file.
Malformed UUIDs and unsafe names return 400; absent or foreign-thread files
return 404. Symlinks, absolute paths, separators, traversal, and directory
targets remain rejected. Media types are selected from the accepted upload
extensions (`.txt`, `.md`, `.pdf`, `.docx`, `.xlsx`) without content sniffing.
No directory listing or arbitrary upload path endpoint is added.

## Experience Design

The interface remains a quiet, operational research workspace. It does not
become a marketing page or a separate evaluation dashboard.

The showcase result uses claims as the primary reading order. On desktop, the
research answer and claims occupy the main column while source coverage,
source details, limitations, and report delivery occupy a narrower inspection
column. Activity remains available below the research result instead of
competing with it.

```text
Session and runtime
Research request and commands
Run state / source progress

Research answer and claims       Source coverage
  claim-1                          Web / MySQL
    all evidence                   Knowledge / Upload
  claim-2                        Source details
    all evidence                 Limitations / reports

Activity timeline
```

On narrow screens the order is request, status, claims, evidence,
limitations, sources, reports, and activity. There is no horizontal scrolling
at 375 CSS pixels.

Each claim uses a native accessible disclosure. The first claim starts open;
the remaining claims start closed. Expanding a claim shows every referenced
evidence record with quote, source title, source kind, and typed locator. The
UI never invents evidence or support scores.

Source coverage uses four stable source-kind rows rather than decorative
metrics. Each row reports collected source/evidence counts or the matching
limitation. Source details show title, capture timestamp, adapter version,
display text, and locator. Web and uploaded-file rows expose only their
validated safe link.

The visual system uses restrained neutral surfaces with ink text, green
completion, blue source links, amber limitations, and red failures. Narrow
source-kind markers encode the actual source category. Claims and source rows
are repeated items, while page-level sections remain unframed bands; the
design does not nest cards inside cards. Typography stays compact and suited
to repeated research work. Long UUIDs, URLs, locators, and evidence wrap
without resizing surrounding controls.

Keyboard focus is visible, native disclosure semantics are preserved, links
have descriptive names, external Web links use `target="_blank"` with
`rel="noreferrer noopener"`, and reduced-motion preferences disable
transitions.

## Empty, Loading, Partial, And Failure States

- Before a showcase run: show the research request surface without an empty
  evaluation panel.
- During citation delivery: show bounded claim/evidence counts when available.
- While loading the document: show a stable live-citation loading state.
- No evidence: render claims with no fabricated evidence and show the
  `no-evidence` or capability limitations.
- Partial sources: render collected sources and each structured limitation.
- Malformed or foreign document: reject the entire document and show
  `Live citation results are unavailable.`
- Degraded delivery: show `Live citation delivery did not complete.` and do
  not request or render a missing document.
- Report preview failure: keep the accepted run result and show the existing
  stable preview-unavailable message.

Raw response bodies, exception representations, absolute paths, credentials,
and unvalidated markup never enter visible state.

## Module Boundary

- `frontend/src/workbench/types.ts`: additive health and live citation types.
- `frontend/src/workbench/api.ts`: live document parser, endpoint client, and
  safe source-link helper.
- `frontend/src/workbench/useWorkbench.ts`: profile-aware citation state,
  event routing, artifact selection, and async guards.
- `frontend/src/workbench/ShowcaseResults.tsx`: claim-first live result,
  source coverage, limitations, and report controls.
- `frontend/src/App.tsx`: profile-aware composition; retain the Phase 4 panel.
- `frontend/src/app.css`: operational two-column/one-column showcase layout.
- `app/api/server.py`: uploaded-source GET route and accepted media types.
- Focused frontend parser/component/hook tests and backend API contract tests.

No general component-system refactor, router, state library, Markdown renderer,
chart package, icon dependency, or new backend persistence layer is added.

## Test Responsibility And Acceptance

Frontend parser tests own document shape, reference integrity, profile-safe
links, malformed values, and foreign threads. Component tests own claim-first
rendering, disclosure behavior, all-evidence association, source coverage,
limitations, link attributes, long text, and empty states. Hook/App tests own
profile routing, event behavior, loading/degraded/error/reset state, artifact
selection, and preservation of Phase 4/tutorial behavior.

Backend integration tests own upload route path/thread isolation, safe content
types, missing files, traversal, symlinks, and the existing live citation API.

The package gate is:

```bash
PYTHONPATH=. UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run pytest \
  tests/integration/phase4_5/test_showcase_delivery_api.py \
  tests/integration/phase2/test_api_contract.py -q

pnpm --dir frontend exec vitest run
pnpm --dir frontend lint
pnpm --dir frontend build

UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run ruff check \
  app/api tests/integration/phase4_5
UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run ruff format --check \
  app/api tests/integration/phase4_5
git diff --check
```

Desktop and mobile browser smoke uses deterministic local data or the
model-unavailable showcase path. It verifies the claim-first order, disclosures,
source links, limitations, report controls, long-content wrapping, no overlap,
and no horizontal overflow. It does not use a real Provider or network source.

## Out Of Scope

- Real model, Tavily, MySQL, or knowledge execution and evidence.
- P4.5-6 capability smoke, acceptance evidence, or portfolio checkpoint.
- Phase 5 orchestration comparisons.
- Citation support scoring for live claims.
- Historical result persistence, routing, sharing, or replay.
- Changes to `/api/citations`, TutorialEvent v1, task terminal ownership, or
  report contents.
