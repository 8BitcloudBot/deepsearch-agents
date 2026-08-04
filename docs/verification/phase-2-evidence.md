# Phase 2 Verification Evidence

> **Current acceptance note — 2026-08-04 (updated):** B1-B4 closure gates
> have all run and B3/B4 are committed. Commit
> `27832bc5c3ba31d23a77e3187bf9e0e016a504c4` (parent `9839440`) containing
> the B3 failure/cancel/rerun tests and the initial B4 documentation was
> pushed to `codex/phase2a-websocket-e2e`; GitHub Actions push run
> **30906797763** (head 27832bc) is **success** — the Python 3.12
> install/tests/lint/format/pre-commit/compose/doctor steps and the
> frontend Node 22 + pnpm 10 job (frozen install, Playwright Chromium
> install, Vitest, lint, build, Playwright browser tests) are all green.
> B2 passed locally (backend API/WS closure 1 passed; mock integration 30
> passed; desktop Playwright happy path 1 passed); B3 passed its gates
> (full Python 353 passed / 11 opt-in skips; B3 focused 11 passed; frontend
> Vitest 24 passed; desktop Playwright 3 passed / 1 project skip; the
> pre-existing Starlette `TestClient` + httpx deprecation warning remains).
> `v0.1-tutorial-parity` has **not** been created and nothing has been
> released; Phase 3-9 remain deferred; default startup is full mock mode
> (no API key) and real Tavily/RAGFlow/model providers are explicit opt-ins
> requiring credentials. The current worktree document edits are an
> evidence-only status refresh (no runtime/test behavior change) and are
> not yet committed; no commit SHA or CI run is claimed for them. See
> [`../phase-status.md`](../phase-status.md) for the current status and
> [“B1-B4 Closure Gates (2026-08-04)”](#b1-b4-closure-gates-2026-08-04)
> below for the exact commands and results. Older rejection labels, commit
> bases, test totals and “remaining blockers” below are chronological
> evidence, not the current status.

> **Historical acceptance note — 2026-08-04 (superseded by the current note
> above):** B1-B4 closure gates had all run. B1 — the Ubuntu Node 22 +
> pnpm 10 CI gate — passed on GitHub Actions push
> run 30878728964 (head `9839440`, remote `codex/phase2a-websocket-e2e` =
> `98394404`): the Python 3.12 job and the frontend Node 22 + pnpm 10 job
> (frozen install, Playwright Chromium install, Vitest, lint, build, Playwright
> browser tests) are all green. B2 passed locally (backend API/WS closure 1
> passed; mock integration 30 passed; desktop Playwright happy path 1 passed).
> B3 passed locally (full Python 353 passed / 11 opt-in skips; B3 focused 11
> passed; frontend Vitest 24 passed; desktop Playwright 3 passed / 1 project
> skip; the pre-existing Starlette `TestClient` + httpx deprecation warning
> remains). **The B3 test files and the B3/B4 documentation changes are NOT
> committed** — they exist only in the local worktree and therefore have no
> remote CI coverage; nothing above claims CI coverage for them. User
> acceptance is pending: the user must review the results and separately
> authorize committing the B3/B4 changes and re-running CI. `v0.1-tutorial-parity`
> has **not** been created and nothing has been released; Phase 3-9 remain
> deferred; default startup is full mock mode (no API key) and real
> Tavily/RAGFlow/model providers are explicit opt-ins requiring credentials.
> See [`../phase-status.md`](../phase-status.md) for the current status and
> [“B1-B4 Closure Gates (2026-08-04)”](#b1-b4-closure-gates-2026-08-04) below
> for the exact commands and results. Older rejection labels, commit bases,
> test totals and “remaining blockers” below are chronological evidence, not
> the current status.

> **Historical note — 2026-08-03 (superseded):** Phase 2 Tasks 0-6 are accepted
> (base HEAD `5988a8a`); Task 7 (documentation, verification, CI) is
> **locally complete but uncommitted** in the worktree — not part of HEAD.
> The full fresh gate passes locally (348 passed, 11 honest skips; frontend
> Vitest/lint/build/Playwright green; Compose MySQL bootstrapped idempotently;
> `PHASE2_MYSQL_INTEGRATION=1` 6 passed; focused E2E 1 passed). Status:
> `blocked_pending_node22_ci` — release and user acceptance are **blocked** until
> the required Node 22 CI frontend gate
> actually runs and passes: **the Ubuntu CI job (Node 22 + pnpm 10) has not been
> run** (the full local gate ran under default Node v26.5.1, bundled v24.14.0; a
> focused frontend rerun under Homebrew Node v22.23.2 with pnpm 11.9.0 passed —
> see “Node 22 local compatibility rerun” below). The `v0.1-tutorial-parity` tag has **not**
> been created and Phase 3 has not started. Task 7 changes remain uncommitted
> in the worktree (worker must not commit; the user authorizes the commit
> after the Node 22 CI gate passes). Older rejection labels, commit bases,
> test totals and “remaining blockers” below are chronological evidence, not
> the current status. See
> [`../phase-status.md`](../phase-status.md) and
> [`../phase-2-tutorial.md`](../phase-2-tutorial.md).

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

## Task 7: Document, Verify, and Stop for Acceptance — 2026-08-03

> **Historical section:** 以下为 Task 7 当时的记录（"未 push"、"Ubuntu CI 未运行"
> 等表述仅指当时）。2026-08-04 之后 Task 7 提交已 push 至远端 head `98394404`，
> B1 实际 Ubuntu CI 已通过；B3/B4 亦已提交为 `27832bc`（push run 30906797763
> success）—— 见文末
> [“B1-B4 Closure Gates (2026-08-04)”](#b1-b4-closure-gates-2026-08-04)。

**Base HEAD:** `5988a8a`（`codex/phase2a-websocket-e2e`）。Task 7 变更**未提交**
（worker 禁止 commit/tag/push；不属于 HEAD `5988a8a`）。
**状态：** Task 7 本地完成；release/用户验收 **blocked** —— 在要求的
Node 22 CI 前端门禁实际运行并通过之前不验收；`v0.1-tutorial-parity` 未创建；
Phase 3 未开始。

### Environment

- **OS:** darwin/arm64（Docker Desktop 29.4.0）
- **Python:** 3.12.7（uv 管理，`requires-python = ">=3.12,<3.13"`）
- **Node:** 默认 v26.5.1（本机）；bundled v24.14.0；Homebrew `node@22`
  v22.23.2（`/opt/homebrew/opt/node@22/bin/node`）可用 —— 本地 Node 22
  聚焦兼容重跑已通过（见下文），但 **Ubuntu CI job（Node 22 + pnpm 10）
  尚未运行**（前端 release 门禁必须在验收前于 CI 执行）
- **uv:** 0.11.7 环境；Playwright Chromium 使用本机已缓存浏览器
- 安装版本（与 ADR 0003 一致）：deepagents 0.6.12、langgraph 1.2.9、
  langchain-core 1.5.1、langchain-openai 1.4.1、tavily-python 0.7.26、
  ragflow-sdk 0.26.0、sqlglot 29.0.1、pypdf 6.14.2、python-docx 1.2.0、
  openpyxl 3.1.5、reportlab 4.5.1、httpx 0.28.1、mysql-connector-python 9.7.0

### Fresh Gate — exact commands and exits

| # | Command | Exit | Result |
|---|---------|------|--------|
| 1 | `uv sync --extra dev --frozen` | 0 | Python 3.12.7 venv 创建（`.venv` 已 ignore） |
| 2 | `.venv/bin/python -m pytest tests/ -q` | 0 | **348 passed, 11 skipped, 1 warning** |
| 3 | `.venv/bin/ruff check app examples tests scripts` | 0 | All checks passed |
| 4 | `.venv/bin/ruff format --check app examples tests scripts` | 0 | 83 files already formatted |
| 5 | `.venv/bin/pre-commit run --all-files` | 0 | ruff / ruff-format / detect-secrets 3/3 Passed（未运行会改写 baseline 的 `detect-secrets scan`） |
| 6 | `pnpm --dir frontend exec vitest run` | 0 | 2 files, **22 passed** |
| 7 | `pnpm --dir frontend lint` | 0 | eslint clean |
| 8 | `pnpm --dir frontend build` | 0 | tsc -b && vite build，built in 3.26s |
| 9 | `pnpm --dir frontend exec playwright install chromium` | 0 | 本机缓存命中，无新下载 |
| 10 | `pnpm --dir frontend exec playwright test` | 0 | **2 passed, 2 skipped**（跳过为有意设计：desktop 流程测试在 mobile project 跳过，mobile 布局测试在 desktop project 跳过） |
| 11 | `docker compose config` | 0 | valid |
| 12 | `docker compose up -d mysql` + healthcheck | healthy | mysql:8.0，host 3307→container 3306 |
| 13 | bootstrap `010_tutorial.sql`（见下） | 0 | 幂等：连续执行 3 次均 exit 0 |
| 14 | `PHASE2_MYSQL_INTEGRATION=1 .venv/bin/python -m pytest tests/integration/phase2/test_mysql_provider.py -q` | 0 | **6 passed** |
| 15 | `.venv/bin/python -m pytest tests/e2e/phase2/test_tutorial_closure.py -q` | 0 | **1 passed**（+ 既有 Starlette deprecation warning） |
| 16 | `.venv/bin/python scripts/doctor.py --offline` / `--mysql` | 0 | offline OK；`phase_0_health` 含 'ok'（Phase 0 表在保留卷中完好） |
| 17 | `git diff --check` | 0 | clean |

1 warning 为既有 Starlette `TestClient` + httpx deprecation，非阻塞。

### Node 22 local compatibility rerun (follow-up, 2026-08-03)

上方 Fresh Gate 全量门禁在默认 Node v26.5.1 下执行；本小节记录新完成的聚焦
前端兼容重跑（工具链更接近 CI：Node 22 + pnpm），**不是**实际 Ubuntu CI。

- **工具链与版本：** `PATH=/opt/homebrew/opt/node@22/bin:$PATH node --version`
  → `v22.23.2`（Homebrew `node@22`，`/opt/homebrew/opt/node@22/bin/node`）；
  默认 shell Node 仍为 v26.5.1、bundled v24.14.0；pnpm 11.9.0
  （`COREPACK_ENABLE_NETWORK=0` —— pnpm 10 本地未缓存，未尝试网络下载）。
- **命令与结果（全部 `COREPACK_ENABLE_NETWORK=0`）：**
  - `pnpm install --offline --frozen-lockfile --dir frontend` → 0，already up to date
  - `pnpm --dir frontend exec vitest run` → 0，2 files，**22 passed**
  - `pnpm --dir frontend lint` → 0，clean
  - `pnpm --dir frontend build` → 0，通过
  - `pnpm --dir frontend exec playwright test` → 0，**2 passed + 2 个有意的
    跨 project 跳过**（desktop/mobile project 路由跳过，与后端无关）
  - `git diff --check` → 0，clean
- **工作树状态不变：** 无新增 tracked/untracked 变更；仅既有 ignored 的
  frontend build/test 产物被刷新。
- **边界：** 这是本地兼容性证据；实际 Ubuntu CI（Node 22 + pnpm 10）job
  **尚未执行**，release/验收仍为 `blocked_pending_node22_ci`。

### Skip enumeration (11, all honest opt-ins)

- `tests/integration/phase1/test_real_model_smoke.py` ×2 — `MODEL_API_KEY not set`（Phase 1 既有）
- `tests/integration/phase2/test_external_provider_smoke.py` ×2 — `PHASE2_TAVILY_SMOKE` / `PHASE2_RAGFLOW_SMOKE` not set
- `tests/integration/phase2/test_mysql_provider.py` ×6 — `PHASE2_MYSQL_INTEGRATION` not set（全量 run 未开启；聚焦 run 见 #14 全过）
- `tests/integration/phase2/test_real_model_smoke.py` ×1 — `PHASE2_REAL_MODEL_SMOKE` + `MODEL_API_KEY` not set

未运行的外部 smoke（需要显式 opt-in + 凭据，本次不执行）：真实模型/DeepAgents
runtime、Tavily、RAGFlow。

### Compose MySQL: preserved volume facts

- 保留卷（`mysql_data`）初始状态：root 无密码、无 `research_copilot` 数据库
  （数据目录早于 `MYSQL_DATABASE` 配置创建）。容器 entrypoint 完成初始化后，
  卷状态与 compose 契约一致（root/root、`research_copilot` 含 Phase 0
  `phase_0_health`）。
- 引导命令（`docker/mysql/init/010_tutorial.sql` 原文，未改动）连续执行 3 次，
  全部 exit 0 —— 幂等成立；`tutorial_reader` 由 `CREATE USER IF NOT EXISTS`
  + `ALTER USER` 管理。
- `tutorial_reader` 验证：`SELECT COUNT(*) FROM drugs` → `3`；
  `INSERT INTO drugs ...` → `ERROR 1142 (42000): INSERT command denied to
  user 'tutorial_reader'@'localhost' for table 'drugs'`（SELECT-only 成立）。
- 保留卷缺数据库时的一次性非破坏步骤记录在 runbook §4.3
  （`CREATE DATABASE IF NOT EXISTS research_copilot`）。

### Stop-condition confirmation

1. 无新依赖/服务/路由/事件字段/provider 模式/前端功能被加入（仅 6 个允许文件）。
2. 无绝对路径、凭据、上传内容或 Provider 响应体进入事件（既有脱敏契约不变）。
3. 离线测试无模型/网络/RAGFlow/宿主机 MySQL 依赖（348 全量离线通过）。
4. 未运行外部 smoke（honest skip，未执行）。
5. **本地 Node 22（v22.23.2）聚焦兼容门禁已通过，但 Ubuntu CI（Node 22 +
   pnpm 10）gate 未运行**：已如实记录为验收前必须执行的 gate（不伪造
   “已通过”；pnpm 10 未缓存、未尝试下载）。
6. 既有非 Phase 2 测试无回归（全量通过）。
7. 未开始 Phase 2B/2C/3；未创建 `v0.1-tutorial-parity`。
8. 除预存 untracked 文件外工作树干净；Task 7 的 6 个允许文件改动未提交。

## B1-B4 Closure Gates — 2026-08-04

> 本节是 B1-B4 封版门禁的现行记录。B3/B4 已提交为
> `27832bc5c3ba31d23a77e3187bf9e0e016a504c4`（parent `9839440`）并 push；
> GitHub Actions push run **30906797763**（head 27832bc）**success**，B3
> 测试与初始 B4 文档的远端 CI 全部通过。B3/B4 小节内的“未提交 / 无远端
> CI 覆盖”表述是提交前的历史记录，已不适用（见上方 Historical note）。

### B1 — Ubuntu CI gate（completed）

Task 7 提交已由用户授权 push；远端 `codex/phase2a-websocket-e2e` head =
`98394404`。GitHub Actions push run **30878728964**（head `9839440`）：
**success**，全部步骤通过：

- **Python 3.12 job：** `uv sync --extra dev --frozen` → `uv run python -m pytest
  tests/ -q` → ruff check → ruff format --check → pre-commit（ruff /
  ruff-format / detect-secrets）全绿。
- **frontend job（Node 22 + pnpm 10）：** frozen install（`pnpm install
  --frozen-lockfile`）→ `playwright install --with-deps chromium` → Vitest →
  lint → build → Playwright browser tests 全绿。

该 run 覆盖的是已提交的 Task 7 状态（历史 gate）；B3/B4 状态由 push run
30906797763（head 27832bc，success）覆盖。

### B2 — Reproducible happy path（completed，本地）

默认 mock 模式（runtime + web + catalog + knowledge 均 "mock"，无 API key）
从输入/约束文件到 Markdown/PDF 预览和下载的闭环复现：

| Command | Result |
|---|---|
| 后端 API/WS closure（`tests/e2e/phase2/test_tutorial_closure.py`） | **1 passed** |
| mock integration（`tests/integration/phase2/test_mock_providers.py` + `test_mock_runtime.py` + `test_websocket_flow.py` + `test_api_contract.py`） | **30 passed** |
| desktop Playwright happy path（`frontend/e2e/tutorial-workbench.spec.ts`，desktop project） | **1 passed** |

### B3 — Failure/cancel/rerun（completed；已提交 `27832bc`，远端 CI 通过）

provider failure、user cancel、duplicate cancel、failure 后 rerun 的终态唯一性
与 React 可再次 Run：

| Command | Result |
|---|---|
| 全量 Python `uv run python -m pytest tests/ -q` | **353 passed, 11 opt-in skips** |
| B3 focused（`tests/unit/phase2/test_task_registry.py` + `tests/integration/phase2/test_failure_cancel_rerun.py` + `tests/e2e/phase2/test_failure_cancel_rerun_closure.py`） | **11 passed** |
| frontend Vitest（`pnpm --dir frontend exec vitest run`） | **24 passed** |
| desktop Playwright（`pnpm --dir frontend exec playwright test`，desktop project） | **3 passed, 1 project skip** |

- 每个场景只产生一个终态事件（task_failed / task_cancelled / task_completed），
  无重复终态；FlakyWebProvider 失败一次后成功（rerun 证据）。
- 既有 Starlette `TestClient` + httpx deprecation warning 仍存在（非阻塞）。
- **提交与 CI（2026-08-04）：** `tests/integration/phase2/test_failure_cancel_rerun.py`、
  `tests/e2e/phase2/test_failure_cancel_rerun_closure.py` 与初始 B4 文档已提交为
  `27832bc5c3ba31d23a77e3187bf9e0e016a504c4`（parent `9839440`）并 push；
  GitHub Actions push run **30906797763**（head 27832bc）**success**：Python
  3.12 install/tests/lint/format/pre-commit/compose/doctor 全绿 + frontend
  Node 22 + pnpm 10 frozen install / Chromium install / Vitest / lint / build /
  Playwright browser tests 全绿。提交前"未获远端 CI 覆盖"的表述仅适用于历史
  状态（见上方 Historical acceptance note）。

### B4 — Evidence closure（completed；初始文档已提交于 `27832bc`）

README、phase-status、phase-2-evidence、CHANGELOG 已统一为 2026-08-04 事实：

- 默认 mock 启动（无 API key）；真实 provider（Tavily / RAGFlow / 真实模型）
  为显式 opt-in 且需要凭据；外部 smoke 未运行。
- B1 远端 CI 通过（run 30878728964，历史 gate）；B2/B3 本地通过；B3/B4 已提交
  `27832bc`，push run 30906797763 success（远端 CI 覆盖 B3 测试与初始 B4 文档）。
- Phase 3-9 deferred；`v0.1-tutorial-parity` 未创建、未 release。
- 后续：用户最终发布验收（创建 tag / release）。当前工作树的文档改动为
  evidence-only 状态刷新，不改变 runtime/test behavior，尚未提交。
