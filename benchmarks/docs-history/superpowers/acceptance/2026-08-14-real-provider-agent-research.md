# Real-Provider Agent Research Acceptance

**Date:** 2026-08-14

**Scope:** Local loopback API and React application using the configured
OpenAI-compatible model, Tavily, local knowledge index, and non-sensitive
session uploads. No deployment, publication, push, or release was performed.

## Accepted Rows

| Row | Result | Source outcome | Delivery |
|---|---|---|---|
| LLM + Web | completed | Web matched; 5 queries, 18 evidence, 7 cited | schema `4.0.0`; JSON, Markdown, PDF |
| LLM + Web + upload | completed | Web matched; upload matched as 2 bounded spans | schema `4.0.0`; JSON, Markdown, PDF |
| Selected MySQL | completed | MySQL matched; 1 executed SQL query, 9 evidence | schema `4.0.0`; JSON, Markdown, PDF; one `task_completed` terminal |
| Local knowledge selected | completed | one real retrieval, `no-match` | truthful no-match plus all three artifacts |
| LLM-only | completed | external sources `not-selected`; upload `no-reference` | explicit evidence limitations plus all three artifacts |
| Cancellation | completed | running task reached one `task_cancelled` terminal | no duplicate terminal |
| Desktop and mobile | completed | `1280` and `375x812`; no horizontal overflow | source controls and progress remained readable |

The Web row retained a real coverage-gap limitation when the reviewer requested
questions that normalized to already executed queries. The coordinator stopped
that no-progress refinement instead of issuing duplicate searches.

The MySQL run used a one-time `MYSQL_ALLOWED_TABLES` configuration and only
executed according to that allowlist. Its diagnostic trace recorded one SQL execution and metadata tool
calls as counts only; no model response or data rows were retained. The source
run remained `matched` after the model-call safety limit, with the executed
query count and every evidence item from that run preserved.

## MySQL Diagnostic Trace

Across the diagnosis and final rechecks, the selected MySQL task recorded
`list_mysql_tables=1`, `describe_mysql_tables=3`, and `inspect_mysql=1` per run.
The observed read-only SQL texts were `SELECT * FROM drugs ORDER BY id`,
`SELECT * FROM drugs LIMIT 50`, and `SELECT * FROM drugs`; each returned 3 rows.
The triggering safety classification was `model-calls`, and no original model
response or database row was retained.

## Defects Found And Closed

- SDK default retries expanded one 30-second model timeout into roughly 90
  seconds. Product model calls now use no implicit retries and a 60-second
  single-stage timeout.
- The Web expert loop repeatedly reached a fixed two-tool budget. Web and local
  knowledge now execute planner-owned evidence questions directly through the
  application adapters.
- Evidence-gap refinement repeated without new queries or evidence. The
  coordinator now stops on no progress.
- Synthesis received every long evidence body. It now receives a cross-source
  representative view of at most 8 items and 1200 characters per quote; the
  full evidence set remains in the canonical document and reports.
- Valid uploads longer than 2048 characters were misclassified as read
  failures. Uploaded content now produces multiple bounded, unique character
  spans.
- A MySQL worker that produced evidence before a model-call safety limit was
  previously reported with `query_count=0`. Budget exceptions now carry the
  executed query count through the worker and coordinator while retaining the
  evidence.

## Deterministic Gates

- Backend: `979 passed, 10 skipped`; one Starlette/httpx deprecation warning.
- Frontend: `59 passed`; TypeScript, ESLint, and Vite production build passed.
- Static: Ruff check and format check passed for `app` and `tests`.
- Repository: legacy product entry scan and `git diff --check` passed.

These results prove the stated local contracts and observed acceptance rows,
including the explicitly allowlisted MySQL run.
They do not claim model quality, retrieval accuracy, latency SLA, cost, or
production readiness.
