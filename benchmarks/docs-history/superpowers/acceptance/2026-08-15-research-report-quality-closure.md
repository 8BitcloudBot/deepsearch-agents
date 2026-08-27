# Research Report Quality Closure Acceptance

**Date:** 2026-08-15

**Scope:** Same-question real Web research through the local loopback API and
React workspace, using the configured model and Tavily. The run recorded only
safe status, count, and artifact metadata; no model response, evidence body,
source URL, query text, or business row was retained here.

## Real Web Row

| Check | Result |
|---|---|
| Terminal events | `1`; `task_completed` |
| Web source | `matched`; attempts `2`; queries `6`; evidence `21`; cited evidence `8` |
| Document | `claims=19`; cited evidence IDs all resolve to retained evidence |
| Answer/Markdown | no code fence or internal synthesis fields; claim and evidence identities preserved |
| Limitations | coverage limitations, when present, resolve to plan question text |
| Artifacts | `research-citations.json`, `research-report.md` only |

## Presentation Checks

- Desktop viewport `1280x720` and emulated narrow viewport `375x812` had no
  horizontal overflow.
- A terminal run marks all five progress stages complete and leaves no active
  stage.
- Answer paragraphs render naturally; claims and evidence are the primary
  result area.
- Cited sources are shown before supplemental sources; supplemental sources and
  process diagnostics are collapsed by default.
- Process diagnostics merge source attempts and coverage rounds, expose only
  attempt/query/hit/evidence counts, and omit query text and raw model/provider
  content.
- Console inspection found no application errors.

## Ten-Case Continuation

The mixed Web + MySQL + local knowledge cases were run sequentially through the
same loopback API. Each row reached exactly one `task_completed` terminal and
produced only `research-citations.json` and `research-report.md`.

| Case | Source outcomes (queries/evidence) | Document | Limitations |
|---|---|---|---|
| 8 | Web `matched` (1/5); MySQL `matched` (1/12); knowledge `matched` (2/14) | `evidence=31`; `claims=5`; `cited=6` | `coverage-gap` |
| 9 | Web `matched` (4/19); MySQL `matched` (1/27); knowledge `matched` (6/24) | `evidence=70`; `claims=9`; `cited=11` | `coverage-gap` |
| 10 | Web `matched` (5/24); MySQL `matched` (1/12); knowledge `matched` (8/26) | `evidence=62`; `claims=8`; `cited=9` | `research-budget-exhausted`, `coverage-gap` |

For all three rows, every cited evidence ID resolved to retained evidence, the
answer contained no code fence or internal synthesis field, and the public
artifact identity remained consistent.

## Offline Gates

- Backend: `1002 passed, 10 skipped`; one existing Starlette/httpx deprecation
  warning.
- Frontend: `64 passed`; TypeScript, ESLint, and Vite production build passed.
- Ruff and `git diff --check` passed.

This record confirms the report-quality closure and two-artifact contract. It
does not claim model quality, retrieval accuracy, latency, cost, SLA, or
production readiness. No commit, push, release, publication, deployment, or
PDF artifact was produced.

## Beginner v2 Rerun (2026-08-16)

The new beginner-oriented dataset and local knowledge collection were exercised
through the loopback API after the MySQL worker prompt was tightened to match
the two-query safety bound. The following rows record only status, counts, and
artifact names; no query text, model response, URL, or business row was kept.

| Case | Selected sources | Document | Source counts (queries/evidence/cited) | Limitations |
|---|---|---|---|---|
| 6 | Web + MySQL | `claims=4`, `evidence=39`; JSON + Markdown | Web `1/5/4`; MySQL `2/34/3` | `coverage-gap` |
| 7 | Web + MySQL | `claims=3`, `evidence=11`; JSON + Markdown | Web `1/5/4`; MySQL `1/6/4` | none |
| 8 | Web + MySQL + knowledge | `claims=1`, `evidence=34`; JSON + Markdown | Web `1/5/2`; MySQL `2/12/0`; knowledge `4/17/0` | `mysql-policy`, `coverage-gap` |
| 9 | Web + MySQL + knowledge | `claims=1`, `evidence=294`; JSON + Markdown | Web `1/5/1`; MySQL `2/280/0`; knowledge `4/9/0` | `mysql-truncated`, `coverage-gap` |
| 10 | Web + MySQL + knowledge | `claims=7`, `evidence=374`; JSON + Markdown | Web `1/5/3`; MySQL `2/360/0`; knowledge `4/9/0` | `mysql-truncated`, `coverage-gap` |

All five rows returned the two expected artifacts, non-empty claims, and at
least one cited evidence item. The three-source rows also show that matched
evidence is not necessarily selected by synthesis for a claim; this remains a
report-quality observation rather than a success-rate claim.
