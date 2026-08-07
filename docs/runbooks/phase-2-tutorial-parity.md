# Phase 2C Runbook — Local Mock Reproduction & Release Evidence

**Purpose:** reproduce the Phase 2 tutorial-parity closed loop locally with mock
providers (no API keys, no network), observe events over WebSocket, download
Markdown/PDF artifacts, and re-run the exact verification gates. Optional
MySQL and real-provider smoke prerequisites are documented at the end; **no
successful external-provider result is claimed in this runbook** — those
smokes remain skipped without credentials (see
[`phase-2-evidence.md`](../verification/phase-2-evidence.md)).

**Baseline:** HEAD `fb17a39` (Phase 2C baseline). The freshest full-gate run is
the B8 integrated acceptance on the Phase 2B working tree at `8dec2b7`
(recorded in the evidence file). The existing tag `v0.1-tutorial-parity`
(tag object `50680e6c`, peeling to commit `e29a80e`) must **not** be created or
moved until user acceptance of Phase 2C.

---

## 1. Prerequisites

| Requirement | Version | Check |
|---|---|---|
| Python | 3.12 (enforced by `scripts/doctor.py --offline`) | `python3 --version` |
| Node.js | 22 (frontend toolchain) | `node --version` |
| pnpm | any recent (lockfile `frontend/pnpm-lock.yaml`) | `pnpm --version` |
| uv | any recent | `uv --version` |
| Docker | only needed for the optional MySQL smoke | `docker --version` |

## 2. Install (offline-safe, no keys)

```bash
uv sync --extra dev --frozen
pnpm --dir frontend install --frozen-lockfile
```

Mock mode needs no `.env` — `Phase2Settings` defaults are all `mock`
(`TUTORIAL_RUNTIME=mock`, `WEB_PROVIDER=mock`, `CATALOG_PROVIDER=mock`,
`KNOWLEDGE_PROVIDER=mock`). Copy `.env.example` → `.env` only when switching to
MySQL or real providers (Section 6).

## 3. Mock Quick Start

```bash
# Terminal 1 — backend
uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000

# Terminal 2 — frontend (http://127.0.0.1:5173)
pnpm --dir frontend dev
```

Sanity checks:

```bash
curl -s http://127.0.0.1:8000/health
# {"status":"ok","service":"research-copilot-api","phase":"2",
#  "tutorial_profile":"tutorial","tutorial_runtime":"mock",
#  "web_provider":"mock","catalog_provider":"mock","knowledge_provider":"mock"}

uv run python scripts/doctor.py --offline   # → "All offline checks passed."
```

The deterministic `MockTutorialRuntime` requires no model key and makes no
network calls; the frontend opens one WebSocket per thread
(`ws://127.0.0.1:8000/ws/{thread_id}`) and renders the event stream.

## 4. Upload → Task → WebSocket → Artifacts

```bash
# 4.1 Upload a constraint (allowed: .txt/.md/.pdf/.docx/.xlsx, max 10 MiB)
TID=$(uuidgen | tr 'A-Z' 'a-z')
printf '# UNIQUE-RUNBOOK-CONSTRAINT-20260807\n\nKeep it short.\n' > /tmp/constraints.md
curl -s -F "thread_id=$TID" -F "files=@/tmp/constraints.md;type=text/markdown" \
  http://127.0.0.1:8000/api/upload
# → 200 {"status":"uploaded","thread_id":"...","files":[{"name":"constraints.md","size":47}]}

# 4.2 Start the task (202 Accepted; duplicate thread_id → 409)
curl -s -X POST http://127.0.0.1:8000/api/task \
  -H 'Content-Type: application/json' \
  -d "{\"query\":\"research aspirin\",\"thread_id\":\"$TID\"}"
# → 202 {"status":"started","thread_id":"..."}

# 4.3 List + download artifacts (PDF must begin %PDF)
curl -s "http://127.0.0.1:8000/api/files?thread_id=$TID"
# → tutorial-report.md + tutorial-report.pdf
curl -sOJ "http://127.0.0.1:8000/api/download?thread_id=$TID&path=tutorial-report.md"
curl -sOJ "http://127.0.0.1:8000/api/download?thread_id=$TID&path=tutorial-report.pdf"
head -c 4 tutorial-report.pdf   # → %PDF

# 4.4 Optional: cancel (200 cancelled/cancelling; unknown id → 404)
curl -s -X POST "http://127.0.0.1:8000/api/task/$TID/cancel"
```

Files are written to `./output/<thread_id>/` (uploads under `./updated/<thread_id>/`)
relative to the uvicorn working directory; `/api/download` only resolves
contained relative paths.

## 5. WebSocket Event Observation

Run from the repo root (uses the `httpx-ws` dev dependency):

```bash
uv run python - <<'EOF'
import asyncio, json
from httpx_ws import aconnect_ws

async def main(tid: str):
    async with aconnect_ws(f"ws://127.0.0.1:8000/ws/{tid}") as ws:
        while True:
            evt = json.loads(await ws.receive_text())
            print(evt["sequence"], evt["type"], evt["message"])
            if evt["type"] in ("task_completed", "task_cancelled", "task_failed"):
                return

asyncio.run(main("REPLACE-WITH-YOUR-TID"))
EOF
```

Expected ordered mock sequence (browser smoke recorded ~28 events):
`task_started` → `agent_started` (`mock-research-agent`) → `tool_started`/
`tool_completed` for `internet_search`, `list_sql_tables`, `preview_table` ×3,
`execute_readonly_query`, `list_knowledge_assistants`,
`ask_knowledge_assistant`, `read_uploaded_file` (only if a file was uploaded),
`generate_markdown_report`, `generate_pdf_report` → `artifact_created`
(`tutorial-report.md`, `tutorial-report.pdf`) → `agent_completed` →
**exactly one** terminal `task_completed`. Sending `{"type":"ping"}` returns
`{"type":"pong"}`. A slow subscriber that overflows the queue is closed with
code `1013` (by design).

## 6. Optional Smokes (all opt-in, all still skipped without credentials)

### 6.1 MySQL catalog (local Docker)

```bash
docker compose up -d mysql          # host port 3307 → container 3306
uv run python scripts/doctor.py --mysql   # phase_0_health must be 'ok'
PHASE2_MYSQL_INTEGRATION=1 uv run pytest tests/integration/phase2/test_mysql_provider.py -q
# Expected: 6 passed (last recorded in the historical final gate)
```

The init scripts seed `drugs`/`inventory`/`sales_records` and create the
SELECT-only `tutorial_reader` account; one test proves the database itself
rejects `INSERT` under that account. To run the app against MySQL, set in
`.env`: `CATALOG_PROVIDER=mysql` (+ `MYSQL_*`). SQL is additionally guarded by
the read-only sqlglot policy (`tests/unit/phase2/test_sql_policy.py`).

### 6.2 Real providers / real model (NOT run this Phase 2C node)

| Smoke | Env prerequisites | Test file |
|---|---|---|
| Tavily | `PHASE2_TAVILY_SMOKE=1` + `TAVILY_API_KEY` | `tests/integration/phase2/test_external_provider_smoke.py` |
| RAGFlow | `PHASE2_RAGFLOW_SMOKE=1` + `RAGFLOW_API_KEY` + `RAGFLOW_BASE_URL` | same file |
| Real model | `PHASE2_REAL_MODEL_SMOKE=1` + `MODEL_API_KEY` (+ `MODEL_NAME`, `MODEL_BASE_URL`) | `tests/integration/phase2/test_real_model_smoke.py` |

Full `deepagents` runtime additionally needs `TUTORIAL_RUNTIME=deepagents` +
`MODEL_API_KEY` in `.env` (the app factory raises without it). Per the B8
evidence, all of these remain skipped without credentials; no external-provider
success has been recorded — do not claim one.

## 7. Exact Verification Commands

Run from the repo root. Expected results below are the B8 recorded values,
re-confirmed by the Phase 2C C2 fresh gate run on this working tree (HEAD
`fb17a39` + C1 doc changes) — all 11 gates GREEN, recorded in
[`phase-2-evidence.md`](../verification/phase-2-evidence.md):

| Gate | Expected |
|---|---|
| `.venv/bin/python -m pytest tests/e2e/phase2/test_tutorial_closure.py -q` | 1 passed |
| `.venv/bin/python -m pytest tests/integration/phase2 tests/unit/phase2 -q` | 355 passed, 9 skipped |
| `pnpm --dir frontend exec vitest run` | 60 passed |
| `pnpm --dir frontend exec eslint src` | clean |
| `pnpm --dir frontend run build` | JS 155.92 kB / CSS 4.50 kB gzip |
| `.venv/bin/ruff check app tests` | clean |
| `.venv/bin/ruff format --check app tests` | 65 files already formatted |
| `docker compose config` | valid |
| `.venv/bin/python scripts/doctor.py --offline` | `All offline checks passed.` |
| `git diff --check` | clean |
| `.venv/bin/pre-commit run --all-files` | all hooks pass after the baseline refresh committed in `fb17a39` |

## 8. Safety Limitations (documented, by design)

- **No persistence/replay:** task registry and event bus are in-memory; a
  backend restart loses tasks, and there is no event history.
- **WebSocket:** live subscriptions only; slow consumer → close `1013`.
- **Isolation:** upload/output dirs are per-thread; `/api/download` rejects
  absolute paths and traversal; terminal events are redacted (no secrets,
  absolute paths, or raw provider responses).
- **Uploads:** allowed extensions `.txt/.md/.pdf/.docx/.xlsx`, 10 MiB cap,
  content-type checks; xlsx/pdf/docx parsing guards (ZIP bomb, macro).
- **Catalog:** SELECT-only DB account + read-only SQL policy.
- **Exactly one terminal event** (`task_completed` / `task_cancelled` /
  `task_failed`) per task.
- Non-goals carried to later phases: persistence/recovery, trace/metrics,
  approval/budget governance, citation validation.

## 9. Phase 2C Release Checklist

- [x] README updated with runbook link
- [x] Runbook records mock quick start, MySQL + real-provider smoke prereqs
- [x] Fresh mock quick start verified: health, upload, task `202`, 28 WebSocket events, artifacts and downloads
- [x] MySQL integration explicitly skipped (`6 skipped`) because Docker is unavailable
- [x] Optional Provider/model smokes explicitly skipped (`3 skipped`) because credentials are absent
- [x] Known limitations and unrun external smokes recorded
- [x] Full gates re-run green on the Phase 2C working tree (Section 7) — C2 fresh run 2026-08-07, all 11 GREEN
- [x] CI parity recorded: `.github/workflows/ci.yml` runs these gates on push/PR to `main` (pytest `tests/`, ruff check/format, `pre-commit` incl. detect-secrets, `docker compose config`, `scripts/doctor.py --offline`, vitest, eslint, build); `git diff --check` (working-tree check) and the credential-gated smokes (MySQL, real providers) stay local-only — no CI run result is recorded in Phase 2C evidence
- [x] `.secrets.baseline` refresh committed and `pre-commit` passes
- [x] User delegated independent acceptance to Codex; fresh full gates passed
- [ ] Explicit authorization to create/move `v0.1-tutorial-parity`
