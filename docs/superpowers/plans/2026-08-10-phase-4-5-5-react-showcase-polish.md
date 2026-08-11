# P4.5-5 React Showcase Polish Implementation Plan

> **For the current Codex session:** Execute this plan inline with focused TDD
> cycles. Do not dispatch implementation work, call Reasonix/DeepSeek, commit,
> push, tag, release, use a real provider, or use the network.

**Status:** Complete in the current worktree. Verification is recorded in
[`docs/verification/p4-5-5-evidence.md`](../../verification/p4-5-5-evidence.md).

**Goal:** Make the existing React workbench profile-aware and present P4.5 live
research as a claim-first result with all linked evidence, source coverage,
limitations, and showcase reports, while preserving tutorial and Phase 4
evaluation behavior.

**Architecture:** Keep `useWorkbench` as the owner of session, run, WebSocket,
artifact, and late-response state. Add a separate fail-closed live-citation
parser and state branch selected only by `health.app_profile`. Render validated
live documents through one focused `ShowcaseResults` component. Add only the
missing thread-scoped uploaded-source GET route on the backend.

**Tech Stack:** Python 3.12, FastAPI, existing `SessionWorkspace`, React 18,
TypeScript 5.7, native disclosure elements, native Fetch/WebSocket, CSS,
Vitest, Testing Library, pytest, Ruff.

## Global Constraints

- Preserve `/api/citations`, TutorialEvent v1, existing WebSocket event names,
  `/api/files`, `/api/download`, report contents, task terminal ownership, and
  default tutorial/mock behavior.
- Use `health.app_profile` as the only profile-routing signal. Do not infer a
  profile from endpoint failures or request both citation endpoints.
- Keep Phase 4 `citation_completed` parsing and P4.5 live delivery parsing
  separate because their payload contracts differ.
- A live document is accepted only for the current thread and only when all
  structural and reference checks pass. Invalid display links are omitted
  locally without discarding an otherwise valid source.
- Render answer, claims, evidence, limitations, event data, and Markdown as
  text only. Never introduce HTML injection, Markdown rendering, a router,
  state library, chart package, icon dependency, or a component-system refactor.
- Do not implement P4.5-6, call a real model/provider/source, access the
  network, add historical persistence, or change the live citation schema.

---

## File Map

- Modify `app/api/server.py`: add the thread-scoped uploaded-source GET route
  and accepted-extension media types.
- Modify `tests/integration/phase4_5/test_showcase_delivery_api.py`: own upload
  route success, media type, isolation, missing, and unsafe-path contracts.
- Modify `tests/integration/phase2/test_api_contract.py`: retain the established
  malformed UUID/path and symlink security boundary where directly affected.
- Modify `frontend/src/workbench/types.ts`: add `app_profile` and exact live
  citation/state types without changing Phase 4 types.
- Modify `frontend/src/workbench/api.ts`: add the live document parser, safe
  display-link validation, and `/api/live-citations` client.
- Create `frontend/src/workbench/ShowcaseResults.tsx`: render claim-first live
  results, coverage, sources, limitations, and showcase report controls.
- Create `frontend/src/workbench/ShowcaseResults.test.tsx`: own focused live
  parser/rendering/security/accessibility cases.
- Modify `frontend/src/workbench/useWorkbench.ts`: route citation events and
  artifacts by profile, own live loading/error/progress/document state, and
  preserve session/run guards.
- Modify `frontend/src/App.tsx`: compose showcase versus Phase 4/tutorial
  surfaces without changing the existing Phase 4 panel contract.
- Modify `frontend/src/App.test.tsx`: own hook and app-level profile routing,
  event lifecycle, reset, artifact selection, and legacy regression cases.
- Modify `frontend/src/app.css`: add the restrained desktop two-column and
  narrow single-column layout, source markers, wrapping, focus, and reduced
  motion rules.

## Frozen Data And Failure Contracts

Add these TypeScript contracts in `frontend/src/workbench/types.ts`:

```ts
export type AppProfile = "tutorial" | "agent-research" | "showcase";
export type LiveSourceKind = "web" | "mysql" | "knowledge" | "uploaded-file";
export type LiveLocatorKind = "url" | "row" | "chunk" | "span";

export interface LiveLocator {
  kind: LiveLocatorKind;
  value: string;
}

export interface LiveCitationClaim {
  claim_id: string;
  statement: string;
  evidence_ids: string[];
}

export interface LiveEvidence {
  evidence_id: string;
  source_id: string;
  source_kind: LiveSourceKind;
  locator: LiveLocator;
  quote: string;
  content_sha256: string;
  thread_id: string | null;
}

export interface LiveSource {
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

export interface LiveLimitation {
  code: string;
  source_kind: LiveSourceKind | null;
  message: string;
}

export interface LiveCitationDocument {
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

export interface LiveCitationProgress {
  claimCount: number | null;
  evidenceCount: number | null;
}

export type LiveDeliveryStatus = "idle" | "loading" | "completed" | "degraded";
```

Extend `HealthInfo` with `app_profile: AppProfile`. Extend `WorkbenchState`
with the live document, loading/error, delivery status, progress, and a
profile-safe artifact identity. Keep all existing Phase 4 fields intact.

Use these stable visible errors exactly:

```text
Live citation results are unavailable.
Live citation delivery did not complete.
Preview unavailable.
```

Malformed/foreign live responses expose no raw body, exception, locator,
credential, or absolute path. A new run, failed/cancelled terminal event, and a
new session clear stale live document, progress, status, and error state.

---

### Task 1: Close The Uploaded-Source Route

**Files:**

- Modify: `app/api/server.py`
- Modify: `tests/integration/phase4_5/test_showcase_delivery_api.py`
- Modify only if needed for an existing security assertion:
  `tests/integration/phase2/test_api_contract.py`

**Interface:**

```text
GET /api/threads/{thread_id}/uploads/{name}
```

The route validates `thread_id` with `_validate_uuid`, resolves `name` only
through `SessionWorkspace.resolve_upload()`, requires an existing regular file,
and returns `FileResponse` with the safe basename. Unsafe names return 400;
missing, foreign-thread, symlink, and directory targets return 404. Accepted
media types are deterministic: `.txt` -> `text/plain`, `.md` ->
`text/markdown`, `.pdf` -> `application/pdf`, `.docx` -> the OOXML Word type,
and `.xlsx` -> the OOXML spreadsheet type. No content sniffing or directory
listing is added.

- [ ] **Step 1: Write failing route tests**

Add parametrized successful GET cases for all five extensions. Add assertions
for exact thread path, response bytes, media type, and absence of absolute
server paths in headers/body. Add cases for malformed UUID, traversal,
absolute path encoding, slash/backslash separators, unsupported extension,
missing file, other-thread file, directory, and symlink.

- [ ] **Step 2: Verify RED**

Run:

```bash
PYTHONPATH=. UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run pytest \
  tests/integration/phase4_5/test_showcase_delivery_api.py \
  tests/integration/phase2/test_api_contract.py -q
```

Expected: new successful route cases return 404 because the route does not
exist; existing API security and live-delivery tests remain green.

- [ ] **Step 3: Implement the minimal route**

Add a private upload media-type mapping/helper local to `app/api/server.py` and
the one GET route. Catch path-validation failures without exposing their text.
Reject unsupported suffixes even if a file is present. Check symlink/directory
state before returning `FileResponse`.

- [ ] **Step 4: Verify GREEN**

Run the Task 1 command. Expected: route and directly affected API contracts
pass with no provider or network access.

### Task 2: Add Exact Live Types And A Fail-Closed Parser

**Files:**

- Modify: `frontend/src/workbench/types.ts`
- Modify: `frontend/src/workbench/api.ts`
- Create: `frontend/src/workbench/ShowcaseResults.test.tsx`

**Interfaces:**

```ts
export function parseLiveCitationDocument(
  value: unknown,
  expectedThreadId: string
): LiveCitationDocument;

export async function getLiveCitations(
  baseUrl: string,
  threadId: string
): Promise<LiveCitationDocument>;
```

`getLiveCitations` requests exactly
`/api/live-citations?thread_id=<encoded-current-thread>`, requires the response
wrapper `thread_id` to equal the requested thread, and passes `document` to the
parser.

The parser requires:

- exact schema version and exact three-element artifact tuple;
- a UUID document thread equal to `expectedThreadId`;
- non-empty, unique source/evidence IDs and sequential `claim-1..claim-N` IDs;
- source/locator pairs `web/url`, `mysql/row`, `knowledge/chunk`, and
  `uploaded-file/span` only;
- evidence source IDs that resolve to a source with matching kind/locator;
- every claim evidence ID to resolve, with no duplicate reference in one claim;
- evidence `thread_id` equal to the current thread only for uploaded files and
  `null` for the other three kinds;
- non-empty bounded scalar fields and a 64-character hexadecimal content hash;
- `execution_mode === "live"` and `evidence_partition === "live"`.

Display-link validation is field-local after structural validation:

- Web: keep only an HTTP/HTTPS URL exactly equal to the URL locator value.
- Uploaded file: keep only
  `/api/threads/<current-thread>/uploads/<encodeURIComponent(basename)>`, where
  the decoded filename is a single safe basename.
- MySQL/knowledge: always omit a link.

Do not derive or repair links from raw locators.

- [ ] **Step 1: Write failing parser/client tests**

Use one deterministic four-source document fixture assembled inside the test.
Assert exact parsing, endpoint URL, current-thread wrapper check, source/evidence
associations, and preservation of valid Web/upload links. Parametrize malformed
schema, artifact tuple, IDs, sequential claims, references, locator pairs,
thread ownership, execution partition, hashes, arrays, and scalar types.
Assert each rejects with only `Live citation results are unavailable.`.

Add field-local cases where javascript/file URLs, credentials, foreign upload
threads, separators, traversal, and MySQL/knowledge links are omitted while the
source remains present.

- [ ] **Step 2: Verify RED**

Run:

```bash
pnpm --dir frontend exec vitest run \
  src/workbench/ShowcaseResults.test.tsx
```

Expected: imports/types fail because the live parser and types do not exist.

- [ ] **Step 3: Implement types, parser, and client**

Use small internal record/string/array validators in `api.ts`. Return newly
constructed typed objects rather than casting the server value. Validate and
copy arrays so unparsed data never reaches React state. Preserve all Phase 4
parser functions unchanged.

- [ ] **Step 4: Verify GREEN**

Run the Task 2 command. Expected: exact parser, wrapper, endpoint, and link
security cases pass.

### Task 3: Add Profile-Aware Live State And Event Routing

**Files:**

- Modify: `frontend/src/workbench/useWorkbench.ts`
- Modify: `frontend/src/App.test.tsx`

**Behavior:**

- `showcase`: parse valid `citation_started` progress; on
  `citation_completed/status=completed`, fetch live citations once for the
  current run; on `status=degraded`, do not fetch and show the stable degraded
  state.
- `agent-research`: retain the existing Phase 4 summary parser and fetch
  `/api/citations` only.
- `tutorial`: retain the existing event timeline and task behavior without
  fetching either citation endpoint.
- A citation event received before health resolves stays on the timeline but
  does not guess a profile or start a citation fetch.
- Existing `sessionRef` and `runRef` guards reject late live documents and late
  artifact previews after a new run/session.

Progress parsing accepts only non-negative integer claim/evidence counts from
the P4.5-4 `citation_started` data. Malformed progress is ignored. Live
`citation_completed` accepts only `completed|degraded`; all other shapes are
ignored without affecting run status.

- [ ] **Step 1: Write failing hook tests**

Add health fixtures for all three profiles. Assert exact endpoint calls,
completed loading/result state, degraded no-fetch state, malformed payload
ignore, foreign event ignore, duplicate event behavior, failed/cancelled clear,
new run/session clear, and late-response rejection. Explicitly prove
agent-research still uses only `/api/citations` and tutorial uses neither.

- [ ] **Step 2: Verify RED**

Run:

```bash
pnpm --dir frontend exec vitest run src/App.test.tsx
```

Expected: showcase state and `/api/live-citations` expectations fail; existing
tutorial and Phase 4 tests continue to identify the compatibility boundary.

- [ ] **Step 3: Implement the separate live state branch**

Add an idempotent `fetchLiveCitations` callback with captured session/run/thread
guards. Route events from the validated health profile without changing the
timeline. Centralize live-state reset beside existing citation/artifact resets.
Do not reinterpret `task_completed`: `TaskRegistry` remains the only owner of
terminal success.

- [ ] **Step 4: Verify GREEN**

Run the Task 3 command. Expected: profile routing, lifecycle, and all existing
hook regressions pass.

### Task 4: Route Showcase Artifacts By Profile

**Files:**

- Modify: `frontend/src/workbench/useWorkbench.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`

**Artifact names:**

```text
showcase        showcase-report.md / showcase-report.pdf
tutorial        tutorial-report.md / tutorial-report.pdf
agent-research  existing Phase 4 citation artifact behavior
```

Continue to accept only server-returned safe basenames. Fetch Markdown preview
as plain text through `/api/download`; build report downloads through the
existing `downloadUrl`. `live-citations.json` may appear in the file list but
is not treated as a Markdown/PDF report.

- [ ] **Step 1: Write failing profile artifact tests**

Assert showcase preview/download URLs use the showcase names and current UUID,
tutorial retains tutorial names, and agent-research retains Phase 4 artifact
links. Add unsafe path and late preview response cases for showcase.

- [ ] **Step 2: Verify RED**

Run the Task 3 frontend command. Expected: showcase report selection fails
because artifact names are currently tutorial-only.

- [ ] **Step 3: Implement profile-specific report selection**

Derive one safe report-name pair from the validated health profile and use it
in refresh/preview/render composition. Do not change `downloadUrl` or trust
document artifact strings as filesystem paths.

- [ ] **Step 4: Verify GREEN**

Run the Task 3 frontend command. Expected: all three profile artifact cases and
legacy artifact security tests pass.

### Task 5: Build The Claim-First Showcase Result

**Files:**

- Create: `frontend/src/workbench/ShowcaseResults.tsx`
- Modify: `frontend/src/workbench/ShowcaseResults.test.tsx`

**Component interface:**

```ts
interface ShowcaseResultsProps {
  document: LiveCitationDocument | null;
  loading: boolean;
  error: string | null;
  deliveryStatus: LiveDeliveryStatus;
  progress: LiveCitationProgress | null;
  apiBaseUrl: string;
  files: FileInfo[];
  markdown: string | null;
  markdownError: string | null;
}
```

The component indexes sources and evidence by validated IDs. Claims are the
primary order. Each claim uses `<details>`, with only the first `open` by
default, and renders every referenced evidence item in `evidence_ids` order.
Evidence shows quote, source title, source kind, and typed locator. It never
computes support scores or fabricates evidence.

The side inspection column always uses the four stable source-kind rows and
shows source/evidence counts or matching limitations. Source details include
title, capture time, version, display text, and locator. Only parser-approved
Web and uploaded-file links are clickable. Web links use `target="_blank"`
and `rel="noreferrer noopener"`; uploaded links remain same-origin/API links.

Render loading, progress, zero evidence, partial source, limitation, malformed,
and degraded states using the frozen messages. Before the first showcase run,
render no empty evaluation dashboard.

- [ ] **Step 1: Write failing component tests**

Assert answer/claim order, first disclosure open, later claims closed, all
evidence associations, all four coverage rows, limitations, source metadata,
valid link labels/attributes, no link for database/knowledge, zero-evidence state,
loading/progress, degraded/error states, long locator/URL text, and raw HTML
rendered as text.

- [ ] **Step 2: Verify RED**

Run:

```bash
pnpm --dir frontend exec vitest run \
  src/workbench/ShowcaseResults.test.tsx
```

Expected: component import/rendering cases fail because it does not exist.

- [ ] **Step 3: Implement the focused component**

Use semantic headings, lists, `<details>/<summary>`, text nodes, and descriptive
links. Keep indexing and presentation local to the component; do not add global
state or mutate the parsed document.

- [ ] **Step 4: Verify GREEN**

Run the Task 5 command. Expected: claim-first, security, partial-state, and
accessibility ownership tests pass.

### Task 6: Compose The Profile-Aware Workbench

**Files:**

- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`

**Composition:**

- Always retain session/runtime, request composer, run status, and activity.
- `showcase`: render `ShowcaseResults` and showcase report controls; do not
  render the Phase 4 evaluation panel.
- `agent-research`: render the existing citation evaluation panel unchanged.
- `tutorial`: retain the accepted tutorial artifact panel and no citation
  evaluation panel.

- [ ] **Step 1: Write failing app composition tests**

For each health profile, render a complete deterministic run and assert the
presence and absence of profile-specific headings, endpoint calls, report
controls, claims, evidence, and evaluation fields. Keep existing Phase 4 claim,
metric, limitation, and citation-artifact assertions unchanged.

- [ ] **Step 2: Verify RED**

Run:

```bash
pnpm --dir frontend exec vitest run src/App.test.tsx
```

Expected: showcase composition fails while legacy profile assertions expose
any accidental regression.

- [ ] **Step 3: Implement additive composition**

Pass only typed hook state into `ShowcaseResults`. Keep the existing Phase 4
panel functions available to agent-research. Update runtime labeling only as
needed to show the validated profile; do not expose configuration secrets.

- [ ] **Step 4: Verify GREEN**

Run the Task 6 command. Expected: all App/hook contracts pass for all profiles.

### Task 7: Apply The Responsive Operational Layout

**Files:**

- Modify: `frontend/src/app.css`
- Modify: `frontend/src/workbench/ShowcaseResults.test.tsx`
- Modify: `frontend/src/App.test.tsx`

**Layout contract:**

- Desktop: research answer/claims main column; coverage/source/limitation/report
  inspection column; activity below the result.
- Narrow viewport: request, status, claims/evidence, limitations, sources,
  reports, activity in one column.
- At 375 CSS pixels: no horizontal overflow; UUIDs, URLs, locators, hashes, and
  preformatted text wrap rather than resize the controls.

Use neutral surfaces, ink text, green completion, blue links, amber
limitations, red failures, and narrow source-kind markers. Preserve visible
keyboard focus, native disclosure behavior, and reduced-motion preferences.
Avoid nested card chrome and decorative metrics.

- [ ] **Step 1: Add structural class-hook assertions**

Assert the showcase main/inspection columns, ordered mobile sections,
source-kind hooks, disclosure hooks, status hooks, and report/activity regions
exist. Do not test browser layout geometry in jsdom.

- [ ] **Step 2: Implement CSS**

Add the smallest rules needed for the approved wide/narrow structure, wrapping,
focus, state color, and `prefers-reduced-motion`. Reuse current typography and
controls where they already satisfy the design.

- [ ] **Step 3: Run focused static frontend checks**

```bash
pnpm --dir frontend exec vitest run \
  src/workbench/ShowcaseResults.test.tsx src/App.test.tsx
pnpm --dir frontend lint
pnpm --dir frontend build
```

Expected: tests, ESLint, TypeScript, and Vite production build pass.

### Task 8: Review And Package Acceptance

**Files:** Review every P4.5-5 diff; update current canonical status documents
only after the code and package gate pass. Do not edit historical handoffs,
plans, or evidence.

- [ ] **Step 1: Review the bounded diff**

Inspect for:

- profile endpoint cross-calls or profile inference from errors;
- weakening of Phase 4 parser, API, WebSocket, or tutorial behavior;
- unsafe/derived links, raw HTML, secret/path leakage, or cross-thread state;
- missing late-response guards and stale live state after reset;
- duplicate assertions without a distinct failure mode;
- P4.5-6 work, unrelated refactors, or new dependencies.

- [ ] **Step 2: Run the backend package gate**

```bash
PYTHONPATH=. UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run pytest \
  tests/integration/phase4_5/test_showcase_delivery_api.py \
  tests/integration/phase2/test_api_contract.py -q

UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run ruff check \
  app/api tests/integration/phase4_5
UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run ruff format --check \
  app/api tests/integration/phase4_5
```

- [ ] **Step 3: Run the frontend package gate**

```bash
pnpm --dir frontend exec vitest run
pnpm --dir frontend lint
pnpm --dir frontend build
```

- [ ] **Step 4: Run whitespace validation**

```bash
git diff --check
```

- [ ] **Step 5: Run deterministic browser smoke**

Start the local API and frontend only with deterministic data or the
model-unavailable showcase path. At desktop and 375-pixel viewports verify:

- claim-first reading order and disclosure interaction;
- every referenced evidence item and four source coverage rows;
- valid Web/upload links and absent MySQL/knowledge links;
- limitations, report preview/download controls, and activity timeline;
- long URL/UUID/locator wrapping, no overlap, and no horizontal overflow;
- keyboard focus visibility and safe loading/degraded/error states.

Do not call a real provider or network source. Stop local processes after the
smoke.

- [ ] **Step 6: Update current package status**

If and only if all package gates pass, update `docs/phase-status.md`,
`docs/roadmap.md`, `docs/phases/phase-4-5-research-showcase.md`, and the
canonical Phase 4.5 plan so P4.5-5 is complete and P4.5-6 is the next package.
Put exact command output/test counts in one new P4.5-5 evidence record only;
do not duplicate counts across current status documents.

## Acceptance Boundary

P4.5-5 is accepted when the uploaded-file display link resolves safely, all
three profiles use only their intended citation/report paths, the showcase
renders validated claims with all evidence and honest partial/failure states,
the focused backend/frontend/static gates pass, and deterministic desktop and
mobile smoke finds no unsafe links or layout overflow.

Acceptance does not authorize P4.5-6, real-provider execution, full release
validation, a commit, push, tag, release, deployment, or remote changes.
