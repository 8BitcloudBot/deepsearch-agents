# Agent Engineering Research Copilot Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Stop after each task's commit and again after the final evidence commit. Do not create the release tag.

**Goal:** Build the `tutorial` profile from tutorial chapters 8-14 as one testable main-agent workflow with Web, controlled MySQL, RAGFlow, file/report delivery, FastAPI, WebSocket, and React closure.

**Architecture:** Keep one application and one `tutorial` profile. Put every varying external dependency behind a small provider interface, then supply real and deterministic mock adapters. A `TutorialRuntime` interface isolates the API task layer from either the real DeepAgents graph or the deterministic offline runtime; both runtimes use the same session, provider, event, and artifact interfaces. One concrete in-memory event bus owns per-thread sequencing and live subscriptions, while the task registry alone owns task lifecycle and terminal events. One `ContextVar[SessionContext]` is the sole source of the current thread/workspace; `RuntimeRequest` carries that same context rather than duplicating directories.

**Tech Stack:** Python 3.12, uv, DeepAgents 0.6.12, LangGraph 1.2.9, LangChain Core 1.5.1, FastAPI, Pydantic, httpx, mysql-connector-python, sqlglot, Tavily Python, RAGFlow SDK, pypdf, python-docx, openpyxl, ReportLab, pytest, React 18, TypeScript, Vite, Vitest, Testing Library, Playwright Chromium, react-markdown, lucide-react, pnpm, Docker Compose, MySQL 8.0.

## Global Constraints

- Implement Phase 2 only. Do not add Phase 3 evaluation data, citation verification, strategy experiments, persistent task/event/checkpoint storage, approvals, trace infrastructure, or cost governance.
- Preserve `deepagents==0.6.12`, `langgraph==1.2.9`, `langchain-core==1.5.1`, and `langchain-openai==1.4.1` unless an installed-signature check proves the lock differs. A version change is a blocker requiring user approval and an ADR update.
- The only profile is `tutorial`; do not create `agent-research` data, prompts, examples, or UI.
- `runtime_mode=mock` is the default and must require no model key or network. `runtime_mode=deepagents` requires an OpenAI-compatible model configuration.
- Web, catalog, and knowledge providers are selected independently: `mock|tavily`, `mock|mysql`, and `mock|ragflow`. A real adapter must never be constructed during module import.
- Provider selection and provenance travel together in an immutable `ProviderBundle`; reports and evidence use its explicit mode fields and never infer mock/real status from concrete Python classes.
- Offline tests must use deterministic adapters and must not call a model, Tavily, RAGFlow, or host MySQL.
- Real-service smoke tests must skip honestly when required configuration is absent. Mock success must never be reported as real-service success.
- Structured data remains controlled and read-only: only `SHOW TABLES`, schema inspection, preview, and one `SELECT`/`WITH ... SELECT` statement are allowed. No DDL, DML, multi-statement query, comments, file functions, or cross-database access.
- MySQL defense is two-layered: sqlglot validates one read-only AST and the application connects as `tutorial_reader`, which has `SELECT` only on `research_copilot.*`. The root account is bootstrap-only and is never used by the provider.
- Uploaded files and generated artifacts are isolated under `updated/session_<thread_id>/` and `output/session_<thread_id>/`. Client input never selects an absolute server path.
- Phase 2 stores tasks and events in memory only. WebSocket disconnect does not cancel a task. A connection receives only events emitted after its subscription; replay cursors, reconnect replay, task recovery, and persistent history belong to Phase 7.
- Baseline HTTP paths remain exactly `POST /api/task`, `POST /api/task/{thread_id}/cancel`, `POST /api/upload`, `GET /api/files`, `GET /api/download`, and `WS /ws/{thread_id}`.
- Every task starts by updating `docs/phase-status.md`, records RED/GREEN and exact command results in `docs/verification/phase-2-evidence.md`, and ends in the listed small Conventional Commit using explicit Git paths.
- Do not copy tutorial source verbatim. The upstream commit inspected for behavioral mapping is `didilili/deepsearch-agents@d0f6eed1e14b1b457942ba2a0195f65731aaf444`.
- Use Node 22 for the frontend release gate. If local Node 22 is unavailable, record that fact and require the Node 22 CI job before acceptance.
- Do not run `detect-secrets scan --baseline`; it mutates the baseline timestamp. Use `.venv/bin/pre-commit run --all-files` as the non-mutating secrets gate.
- The accepted plan and DeepSeek prompt are part of the Task 0 documentation commit. Leaving either planning artifact untracked is a stop condition because the final clean-worktree gate would otherwise be impossible.

---

## Locked File Map

### Backend modules

- `app/settings.py`: immutable Phase 2 settings and environment parsing; no provider construction.
- `app/api/context.py`: one `SessionContext` and one `ContextVar` lifecycle for the current thread/workspace.
- `app/api/events.py`: version-1 `TutorialEvent`, concrete per-thread sequencing, and bounded live subscriptions; no history/replay surface.
- `app/api/schemas.py`: HTTP request/response and artifact schemas.
- `app/api/tasks.py`: in-memory task registry, cancellation, and the sole ownership of task-started/terminal events; depends only on `TutorialRuntime` and `InMemoryEventBus`.
- `app/api/server.py`: FastAPI factory, HTTP routes, WebSocket connection manager, dependency wiring.
- `app/providers/contracts.py`: value objects, three provider protocols, and the provenance-carrying `ProviderBundle`.
- `app/providers/mock.py`: deterministic offline adapters for Web, catalog, and RAGFlow.
- `app/providers/tavily.py`: real Tavily adapter.
- `app/providers/mysql.py`: real controlled MySQL adapter and read-only validation.
- `app/providers/ragflow.py`: real RAGFlow adapter.
- `app/tools/web.py`, `catalog.py`, `knowledge.py`: LangChain tools created from provider interfaces and the concrete event bus.
- `app/tools/files.py`: safe upload parsing from the current workspace.
- `app/tools/reports.py`: Markdown creation and Markdown-to-PDF conversion inside the current workspace.
- `app/agent/prompts.py`: tutorial-only main/subagent prompts as Python constants.
- `app/agent/subagents.py`: the three `SubAgent` dictionaries.
- `app/agent/runtime.py`: `RuntimeRequest`, `RuntimeResult`, `TutorialRuntime`, `MockTutorialRuntime`, and `DeepAgentsTutorialRuntime`.
- `app/agent/factory.py`: `create_tutorial_agent()` using the installed ADR 0002 surface.
- `docker/mysql/init/010_tutorial.sql`: idempotent tutorial catalog schema, seed rows, and `tutorial_reader` grants for fresh volumes and explicit bootstrap of existing volumes.

### Frontend modules

- `frontend/src/types.ts`: exact HTTP, artifact, and event discriminated unions.
- `frontend/src/lib/api.ts`: HTTP helpers and relative artifact download URL.
- `frontend/src/hooks/useTutorialSession.ts`: thread lifecycle, WebSocket, task, upload, cancellation, and artifact refresh.
- `frontend/src/components/TaskComposer.tsx`: query and file selection.
- `frontend/src/components/RunStatus.tsx`: stable status and cancel control.
- `frontend/src/components/EventFeed.tsx`: structured event rendering.
- `frontend/src/components/ArtifactList.tsx`: report list and download actions.
- `frontend/src/components/ReportPreview.tsx`: Markdown preview.
- `frontend/src/App.tsx`, `frontend/src/app.css`: assemble the workbench.
- `frontend/playwright.config.ts`, `frontend/e2e/tutorial-workbench.spec.ts`: Chromium acceptance for the 390px layout and artifact workflow shell.

### Tests and evidence

- `tests/unit/phase2/`: settings, single-context lifecycle, event publication/subscription, SQL AST policy, workspace, report, and factory tests.
- `tests/integration/phase2/`: mock providers/runtime, FastAPI/WebSocket closure, real-service gated smokes.
- `tests/e2e/phase2/test_tutorial_closure.py`: one deterministic Web + catalog + knowledge + uploaded-file report workflow.
- `frontend/src/*.test.tsx`, `frontend/src/hooks/useTutorialSession.test.ts`: UI and protocol acceptance tests.
- `docs/adr/0003-phase-2-tutorial-contracts.md`: provider/runtime/event/API decisions.
- `docs/verification/phase-2-evidence.md`: chronological evidence; distinguish mock, Compose MySQL, and real external results.
- `docs/phase-2-tutorial.md`: startup, provider matrix, sample requests/responses, WebSocket event examples, RAGFlow external setup, and limitations.

## Locked Interfaces

### Provider and runtime interfaces

```python
# app/providers/contracts.py
from dataclasses import dataclass
from typing import Literal, Protocol

@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    content: str

@dataclass(frozen=True)
class SearchResult:
    query: str
    hits: tuple[SearchHit, ...]

@dataclass(frozen=True)
class TableInfo:
    name: str

@dataclass(frozen=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    truncated: bool

@dataclass(frozen=True)
class KnowledgeAssistant:
    name: str
    description: str
    knowledge_bases: tuple[str, ...]

@dataclass(frozen=True)
class KnowledgeAnswer:
    assistant_name: str
    answer: str

class WebSearchProvider(Protocol):
    def search(self, query: str, *, max_results: int = 5) -> SearchResult: ...

class CatalogProvider(Protocol):
    def list_tables(self) -> tuple[TableInfo, ...]: ...
    def describe_table(self, table_name: str) -> QueryResult: ...
    def preview_table(self, table_name: str, *, limit: int = 20) -> QueryResult: ...
    def execute_readonly(self, query: str, *, limit: int = 100) -> QueryResult: ...

class KnowledgeProvider(Protocol):
    def list_assistants(self) -> tuple[KnowledgeAssistant, ...]: ...
    def ask(self, assistant_name: str, question: str) -> KnowledgeAnswer: ...

@dataclass(frozen=True)
class ProviderBundle:
    web: WebSearchProvider
    catalog: CatalogProvider
    knowledge: KnowledgeProvider
    web_mode: Literal["mock", "tavily"]
    catalog_mode: Literal["mock", "mysql"]
    knowledge_mode: Literal["mock", "ragflow"]

    @property
    def uses_mock(self) -> bool:
        return "mock" in (self.web_mode, self.catalog_mode, self.knowledge_mode)
```

```python
# app/api/context.py
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from app.tools.files import SessionWorkspace

@dataclass(frozen=True)
class SessionContext:
    thread_id: str
    workspace: SessionWorkspace

_CURRENT_SESSION: ContextVar[SessionContext | None] = ContextVar(
    "phase2_current_session", default=None
)

@contextmanager
def session_context(context: SessionContext): ...

def current_session() -> SessionContext: ...
```

`session_context()` sets one token and resets it in `finally`; nested scopes restore the outer `SessionContext`. `current_session()` raises a redacted `RuntimeError` when no context is active. `SessionWorkspace.for_thread()` validates the UUID once and returns upload/output directories without exposing a second public thread identifier.

```python
# app/agent/runtime.py
from dataclasses import dataclass
from typing import Protocol

from app.api.context import SessionContext

@dataclass(frozen=True)
class RuntimeRequest:
    query: str
    context: SessionContext

@dataclass(frozen=True)
class RuntimeResult:
    answer: str
    artifacts: tuple[str, ...]  # paths relative to output/session_<thread_id>

class TutorialRuntime(Protocol):
    async def run(self, request: RuntimeRequest) -> RuntimeResult: ...
```

`MockTutorialRuntime` must call the injected `ProviderBundle`, read the first uploaded fixture when present, generate `tutorial-report.md` and `tutorial-report.pdf`, and emit the same agent/tool/artifact event types as the real runtime. It is a deterministic executable fixture, not a second product orchestration strategy. Reports include the three explicit provider mode fields; they never determine provenance with `isinstance()` or class-name checks.

### Event contract

Every server event is JSON with these required keys:

```python
JsonValue = (
    None
    | bool
    | int
    | float
    | str
    | list["JsonValue"]
    | dict[str, "JsonValue"]
)
TutorialEventType = Literal[
    "task_started", "agent_started", "agent_completed",
    "tool_started", "tool_completed", "artifact_created",
    "task_completed", "task_cancelled", "task_failed",
]

class TutorialEvent(BaseModel):
    version: Literal[1] = 1
    sequence: int = Field(ge=1)
    thread_id: str
    type: Literal[
        "task_started", "agent_started", "agent_completed",
        "tool_started", "tool_completed", "artifact_created",
        "task_completed", "task_cancelled", "task_failed",
    ]
    message: str
    data: dict[str, JsonValue] = Field(default_factory=dict)
    timestamp: datetime
```

Rules: `sequence` is monotonic per in-memory thread; `tool_started` and `tool_completed` carry `tool_name`; `agent_started` and `agent_completed` carry `agent_name`; `artifact_created` carries relative `path`, `name`, and `media_type`; terminal events are exactly one of completed/cancelled/failed. No tokens, costs, trace IDs, persisted IDs, replay cursor, citation status, or approval fields are allowed in Phase 2.

The event module is deliberately concrete in Phase 2. There is only one event implementation, so `EventSink`/`EventSource` protocols would be hypothetical seams and are prohibited:

```python
class InMemoryEventBus:
    def emit(
        self,
        thread_id: str,
        event_type: TutorialEventType,
        message: str,
        data: dict[str, JsonValue] | None = None,
    ) -> TutorialEvent: ...

    def subscribe(
        self, thread_id: str
    ) -> AbstractAsyncContextManager[EventSubscription]: ...

@dataclass(eq=False)
class EventSubscription:
    queue: asyncio.Queue[TutorialEvent]
    overflowed: asyncio.Event

```

`InMemoryEventBus.subscribe()` registers an `EventSubscription` with a bounded queue of 256 events before yielding it and always unregisters it in `finally`. `emit()` runs only on the owning application event-loop thread, assigns the sequence without an `await`, and publishes the same event to every live subscriber. It stores only the per-thread next-sequence counter, never event history. When a queue is full, `emit()` removes that subscription and sets `subscription.overflowed`; the WebSocket handler races `queue.get()` against `overflowed.wait()` and closes with code `1013` on overflow while task execution continues. New subscriptions receive future events only. All blocking provider calls run through `asyncio.to_thread()` inside async tool wrappers, and those wrappers emit start/completion only before and after returning to the owning loop; worker threads never call the event bus.

Lifecycle ownership is also fixed: `TaskRegistry.start()` emits `task_started` synchronously before creating the `asyncio.Task`; its private runner emits exactly one of `task_completed`, `task_cancelled`, or redacted `task_failed` in `try/except/finally`. Both runtime implementations emit only `agent_*`, `tool_*`, and `artifact_created`, return or raise, and never emit task lifecycle or terminal events. This rule covers cancellation before the runtime coroutine executes and prevents duplicate terminals.

### HTTP and WebSocket contract

```text
POST /api/task
request:  {"query":"...","thread_id":"optional UUID"}
202:      {"status":"started","thread_id":"UUID"}
409:      same thread_id already has a running task

POST /api/task/{thread_id}/cancel
200:      {"status":"cancelled"|"cancelling","thread_id":"UUID"}
404:      no active task

POST /api/upload (multipart: thread_id, files[])
200:      {"status":"uploaded","thread_id":"UUID","files":[{"name":"constraints.md","size":12}]}
400/413/415: invalid thread, size, or extension

GET /api/files?thread_id=<UUID>
200:      {"thread_id":"UUID","files":[Artifact...]}

GET /api/download?thread_id=<UUID>&path=tutorial-report.md
200:      file bytes; 400 for unsafe path; 404 for missing file

WS /ws/{thread_id}
server:    TutorialEvent objects
client:    {"type":"ping"}
server:    {"type":"pong"}
```

`Artifact` is `{name, path, media_type, size}` and `path` is always relative to that thread's output directory. The server resolves and checks containment; the frontend never sends or receives an absolute server path. Heartbeat `{type:"pong"}` is a separate `HeartbeatMessage` union member and is not stored, sequenced, or treated as a `TutorialEvent`.

## Task 0: Freeze Phase 2 Contracts and Start Evidence

**Files:**
- Modify: `docs/superpowers/plans/2026-07-29-agent-engineering-research-copilot-phase-2-plan.md`
- Modify: `docs/superpowers/plans/2026-07-29-agent-engineering-research-copilot-phase-2-deepseek-prompt.md`
- Create: `docs/adr/0003-phase-2-tutorial-contracts.md`
- Create: `docs/verification/phase-2-evidence.md`
- Modify: `docs/phase-status.md`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `.env.example`

**Interfaces:** Produces the exact versions, settings names, file map, interfaces, event union, and HTTP contracts above. All later tasks consume them unchanged.

- [ ] **Step 1: Verify the start state and installed surfaces**

Run:

```bash
git status --short
git show --no-patch --oneline v0.0-deepagents-examples
.venv/bin/python -c 'import deepagents, langgraph, langchain_core; print(deepagents.__version__, langgraph.__version__, langchain_core.__version__)'
.venv/bin/python -c 'import inspect; from deepagents import create_deep_agent; print(inspect.signature(create_deep_agent))'
```

Expected: only the accepted plan/prompt may be untracked; the tag points to `c6c0fa8`; versions and factory surface agree with ADR 0002. Any other mismatch stops Task 0. Task 0 will track the two accepted planning artifacts so all later tasks start and finish cleanly.

- [ ] **Step 2: Record RED dependency imports**

Run:

```bash
.venv/bin/python -c 'import docx, openpyxl, pypdf, reportlab, ragflow_sdk, sqlglot, tavily'
```

Expected before dependency update: exit nonzero for at least one missing Phase 2 package. Record the exact missing modules.

- [ ] **Step 3: Add the minimal runtime dependencies and settings contract**

Add runtime dependencies with constrained major versions: `httpx>=0.28,<1`, `mysql-connector-python>=9.2,<10`, `python-multipart>=0.0.20,<1`, `sqlglot>=26,<30`, `tavily-python>=0.7,<1`, `ragflow-sdk>=0.1,<1`, `pypdf>=5,<7`, `python-docx>=1.1,<2`, `openpyxl>=3.1,<4`, and `reportlab>=4,<5`. Keep test-only packages in `dev`; Task 6 adds Playwright to frontend dev dependencies. Run `uv lock` and `uv sync --extra dev --frozen`.

Add these documented settings to `.env.example`: `APP_PROFILE=tutorial`, `TUTORIAL_RUNTIME=mock`, `WEB_PROVIDER=mock`, `CATALOG_PROVIDER=mock`, `KNOWLEDGE_PROVIDER=mock`, `MODEL_NAME`, `MODEL_BASE_URL`, `MODEL_API_KEY`, `TAVILY_API_KEY`, `RAGFLOW_BASE_URL`, `RAGFLOW_API_KEY`, `MYSQL_USER=tutorial_reader`, `MYSQL_PASSWORD=tutorial_reader`, and the existing MySQL host/port/database variables. The root Compose credential remains bootstrap-only and is not part of application settings. Never add non-local or secret values.

After syncing, introspect the installed provider surfaces rather than relying on tutorial memory:

```bash
.venv/bin/python - <<'PY'
import inspect
from ragflow_sdk import RAGFlow
from tavily import TavilyClient

print("RAGFlow", inspect.signature(RAGFlow))
print("RAGFlow.list_chats", inspect.signature(RAGFlow.list_chats))
print("TavilyClient", inspect.signature(TavilyClient))
print("TavilyClient.search", inspect.signature(TavilyClient.search))
PY
```

Record the installed versions and signatures in ADR 0003. If imports or public names differ, stop and revise the adapter plan through user review; do not guess or use private SDK APIs.

- [ ] **Step 4: Write ADR 0003 and initialize evidence/status**

ADR 0003 must reproduce the Locked Interfaces without weakening them and state that real adapters are lazy, provider modes are explicit, the event bus has live-only subscriptions, the registry owns task terminals, Phase 2 state is memory-only, the database provider uses a SELECT-only account, and `v0.1` uses relative artifact paths. Set phase status to `in_progress`, Task 0 completed, Task 1 next. Initialize evidence with environment, start SHA, upstream mapping SHA, dependency RED, and an empty chronological gate table.

- [ ] **Step 5: Verify and commit**

```bash
.venv/bin/python -c 'import docx, openpyxl, pypdf, reportlab, ragflow_sdk, sqlglot, tavily'
.venv/bin/python -m pytest tests/ -q
.venv/bin/ruff check app examples tests scripts
git diff --check
git add pyproject.toml uv.lock .env.example docs/adr/0003-phase-2-tutorial-contracts.md docs/verification/phase-2-evidence.md docs/phase-status.md docs/superpowers/plans/2026-07-29-agent-engineering-research-copilot-phase-2-plan.md docs/superpowers/plans/2026-07-29-agent-engineering-research-copilot-phase-2-deepseek-prompt.md
git diff --cached --name-only
git commit -m "docs: freeze phase two tutorial contracts"
```

Expected: imports pass, the existing 83 tests still pass with the two honest real-model skips, and only the eight explicit files are staged.

## Task 1: Build Settings, Live Events, and Deterministic Adapters

**Files:**
- Create: `app/settings.py`, `app/api/events.py`
- Create: `app/providers/__init__.py`, `app/providers/contracts.py`, `app/providers/mock.py`
- Create: `tests/unit/phase2/test_settings.py`, `test_events.py`
- Create: `tests/integration/phase2/test_mock_providers.py`
- Modify: `docs/phase-status.md`, `docs/verification/phase-2-evidence.md`

**Interfaces:** Produces `Phase2Settings`, `TutorialEvent`, concrete `InMemoryEventBus`, `ProviderBundle`, and the provider contracts/mocks in Locked Interfaces.

- [ ] **Step 1: Write RED tests**

Tests must assert: default profile/runtime/providers are tutorial/mock; unsupported values fail with the environment variable name; event sequences returned by `emit()` are `1,2,3` independently per thread; payloads serialize to the locked JSON shape; two live subscribers receive the same event; exiting one subscription unregisters only that queue; a new subscription does not replay prior events; a full queue sets only that subscription's `overflowed` event and does not affect task emission or other subscribers; no public history accessor exists; mock Web returns two fixed HTTPS hits; mock catalog exposes `drugs`, `inventory`, and `sales_records`; mock knowledge exposes one tutorial assistant and one fixed answer; `ProviderBundle.uses_mock` follows explicit mode fields.

```python
def test_sequences_are_isolated_by_thread():
    bus = InMemoryEventBus(clock=lambda: FIXED_TIME)
    assert bus.emit("a", "task_started", "start").sequence == 1
    assert bus.emit("b", "task_started", "start").sequence == 1
    assert bus.emit("a", "tool_started", "web", {"tool_name": "internet_search"}).sequence == 2
```

Run `pytest tests/unit/phase2 tests/integration/phase2/test_mock_providers.py -q`; expected RED is missing Phase 2 modules, not test syntax errors.

- [ ] **Step 2: Implement the locked value objects and adapters**

Use frozen dataclasses for provider results and `ProviderBundle` plus the locked bounded in-memory event bus. `Phase2Settings.from_env(environ: Mapping[str, str])` accepts an injected mapping for tests and validates provider enums without reading `.env` or constructing clients.

Mock adapters return fixed fixtures only. They must reject unknown table/assistant names with `ValueError` and must not import Tavily, MySQL, or RAGFlow modules.

- [ ] **Step 3: GREEN, document, and commit**

```bash
.venv/bin/python -m pytest tests/unit/phase2 tests/integration/phase2/test_mock_providers.py -q
.venv/bin/ruff check app/settings.py app/api app/providers tests/unit/phase2 tests/integration/phase2
.venv/bin/ruff format --check app/settings.py app/api app/providers tests/unit/phase2 tests/integration/phase2
git diff --check
git add app/settings.py app/api/events.py app/providers/__init__.py app/providers/contracts.py app/providers/mock.py tests/unit/phase2/test_settings.py tests/unit/phase2/test_events.py tests/integration/phase2/test_mock_providers.py docs/phase-status.md docs/verification/phase-2-evidence.md
git commit -m "feat: add phase two runtime contracts"
```

## Task 2: Implement Web, Controlled MySQL, and RAGFlow Modules

**Files:**
- Create: `app/providers/tavily.py`, `app/providers/mysql.py`, `app/providers/ragflow.py`
- Create: `app/tools/__init__.py`, `app/tools/web.py`, `app/tools/catalog.py`, `app/tools/knowledge.py`
- Create: `app/agent/__init__.py`, `app/agent/prompts.py`, `app/agent/subagents.py`
- Create: `docker/mysql/init/010_tutorial.sql`
- Create: `tests/unit/phase2/test_sql_policy.py`, `test_subagents.py`, `test_provider_factories.py`, `test_external_adapters.py`
- Create: `tests/integration/phase2/test_mysql_provider.py`, `test_external_provider_smoke.py`
- Modify: `docker-compose.yml`, `docs/phase-status.md`, `docs/verification/phase-2-evidence.md`

**Interfaces:** Produces three lazy real adapters, seven tools (`internet_search`, `list_sql_tables`, `describe_table`, `preview_table`, `execute_readonly_query`, `list_knowledge_assistants`, `ask_knowledge_assistant`), and subagents named `web-research`, `structured-data`, and `knowledge-base`.

- [ ] **Step 1: Write RED policy and assembly tests**

Parametrize accepted SQL (`SELECT ...`, one `WITH ... SELECT`) and rejected SQL (`INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`, `ALTER`, `CALL`, `LOAD_FILE`, `INTO OUTFILE`, comments, semicolons, locking reads, and `other_db.table`). Parse with the MySQL dialect in sqlglot and require exactly one root `Select` or a query whose CTE body and final root are read-only selects; walk every AST node to reject DDL/DML/command/file/lock constructs and catalog qualifiers other than `research_copilot`. Assert preview limits are clamped to 1-100 and table identifiers match `[A-Za-z_][A-Za-z0-9_]*`. Assert each subagent has exactly the locked name, description, prompt, and only its allowed tools. With injected fake SDK clients, assert Tavily normalization, RAGFlow assistant mapping, session deletion after success and error, lazy construction, and credential/provider-body redaction without network access.

```python
@pytest.mark.parametrize("query", [
    "DELETE FROM drugs", "SELECT 1; SELECT 2", "SELECT * FROM other.drugs",
    "SELECT LOAD_FILE('/tmp/x')", "SELECT * FROM drugs -- bypass",
])
def test_readonly_policy_rejects_unsafe_sql(query):
    with pytest.raises(ReadOnlyQueryError):
        validate_readonly_query(query, database="research_copilot")
```

Run the new unit tests; expected RED is missing providers/tools/subagents.

- [ ] **Step 2: Implement lazy adapters and tool factories**

Construct SDK/client objects only inside adapter constructors called by `build_providers(settings)`, which returns the locked `ProviderBundle` with the configured modes. Tavily maps SDK results into `SearchResult`. MySQL connects only with `MYSQL_USER=tutorial_reader`, uses dictionary-free cursors, applies `MAX_EXECUTION_TIME(5000)` to accepted SELECTs, wraps user SQL as `SELECT * FROM (<accepted query>) AS phase2_query LIMIT <limit>` so an existing limit cannot bypass the maximum, and returns `QueryResult`; database credentials never enter exceptions/events. RAGFlow uses only the Task 0 introspected public API, lists Chat assistants, creates one temporary session per `ask`, deletes it in `finally`, and maps the answer into `KnowledgeAnswer`.

Each `create_*_tools(provider, events)` function returns async LangChain tools that emit paired `tool_started`/`tool_completed` events on the application loop, execute the blocking provider method via `asyncio.to_thread()`, and expose only normalized results to the agent. Never put result bodies or credentials in events, and never call the event bus from a provider worker thread.

- [ ] **Step 3: Seed and verify controlled MySQL**

`010_tutorial.sql` is idempotent: it creates only `drugs`, `inventory`, and `sales_records`, replaces their small deterministic seed rows inside a transaction, runs `CREATE USER IF NOT EXISTS` followed by `ALTER USER` for `tutorial_reader` at `%`, revokes all privileges, grants only `SELECT` on `research_copilot.*`, and flushes privileges. Keep the existing database and host port 3307.

Docker init scripts run only for a new data directory, while the accepted Phase 1 MySQL volume is intentionally preserved. Therefore every Task 2 execution must explicitly bootstrap the existing volume without deleting it:

```bash
docker compose up -d mysql
docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"' < docker/mysql/init/010_tutorial.sql
docker compose exec -T mysql sh -c 'mysql -ututorial_reader -ptutorial_reader "$MYSQL_DATABASE" -e "SELECT COUNT(*) FROM drugs"'
```

The provider test is marked `integration` and skips unless `PHASE2_MYSQL_INTEGRATION=1`; when enabled it asserts table discovery, schema, preview, a join/aggregate SELECT, truncation, and a direct provider write attempt rejected by policy. Add a separate database-permission assertion that connects as `tutorial_reader`, attempts `INSERT`, receives MySQL access denied, rolls back, and confirms the row count is unchanged. Never use `docker compose down -v` or delete/recreate the existing volume.

- [ ] **Step 4: Add honest external smoke gates**

`test_external_provider_smoke.py` contains separate tests gated by `PHASE2_TAVILY_SMOKE=1` and `PHASE2_RAGFLOW_SMOKE=1`. Each also checks required configuration and calls exactly one low-cost operation. Missing opt-in/config is a skip; configured failure is a failure.

- [ ] **Step 5: GREEN and commit**

```bash
.venv/bin/python -m pytest tests/unit/phase2/test_sql_policy.py tests/unit/phase2/test_subagents.py tests/unit/phase2/test_provider_factories.py tests/unit/phase2/test_external_adapters.py -q
docker compose up -d mysql
docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"' < docker/mysql/init/010_tutorial.sql
PHASE2_MYSQL_INTEGRATION=1 .venv/bin/python -m pytest tests/integration/phase2/test_mysql_provider.py -q
.venv/bin/python -m pytest tests/integration/phase2/test_external_provider_smoke.py -q
.venv/bin/ruff check app tests docker
.venv/bin/ruff format --check app tests
git diff --check
git add app/providers/tavily.py app/providers/mysql.py app/providers/ragflow.py app/tools/__init__.py app/tools/web.py app/tools/catalog.py app/tools/knowledge.py app/agent/__init__.py app/agent/prompts.py app/agent/subagents.py docker/mysql/init/010_tutorial.sql docker-compose.yml tests/unit/phase2/test_sql_policy.py tests/unit/phase2/test_subagents.py tests/unit/phase2/test_provider_factories.py tests/unit/phase2/test_external_adapters.py tests/integration/phase2/test_mysql_provider.py tests/integration/phase2/test_external_provider_smoke.py docs/phase-status.md docs/verification/phase-2-evidence.md
git commit -m "feat: add tutorial research providers"
```

If Compose MySQL cannot start, stop before commit and record the exact blocker; do not replace its evidence with mock output.

## Task 3: Add Safe Workspace and Report Delivery

**Files:**
- Create: `app/api/context.py`, `app/tools/files.py`, `app/tools/reports.py`
- Create: `tests/unit/phase2/test_context.py`, `test_workspace.py`, `test_file_reader.py`, `test_reports.py`
- Modify: `.gitignore`, `docs/phase-status.md`, `docs/verification/phase-2-evidence.md`

**Interfaces:** Produces `SessionWorkspace`, the single `SessionContext`/ContextVar lifecycle, `read_uploaded_file`, `generate_markdown_report`, `generate_pdf_report`, and `Artifact` metadata. All paths exposed outside this module are relative artifact paths.

- [ ] **Step 1: Write RED containment and format tests**

Cover safe filenames; the exact same-session duplicate policy (the last complete upload atomically replaces the prior file); `../`; absolute paths; symlink escape; mismatched extension/content type/header; unsupported suffix; size over 10 MiB; PDF over 200 pages; and parsing of `.txt`, `.md`, `.pdf`, `.docx`, and `.xlsx`. Context tests assert one active `SessionContext`, nested restoration, reset after success/error, and `current_session()` failure outside a scope. Report tests assert UTF-8 Markdown content and a PDF beginning with `%PDF`; artifact paths are `tutorial-report.md` and `tutorial-report.pdf`, never absolute.

```python
def test_workspace_rejects_parent_traversal(tmp_path):
    workspace = SessionWorkspace(
        tmp_path / "updated",
        tmp_path / "output",
        "00000000-0000-4000-8000-000000000001",
    )
    with pytest.raises(UnsafeWorkspacePath):
        workspace.resolve_upload("../secret.txt")
```

- [ ] **Step 2: Implement workspace and file readers**

`SessionWorkspace.for_thread()` validates the server-assigned UUID before forming `session_<thread_id>` and returns only `upload_dir`/`output_dir`; callers get the thread identifier from the enclosing `SessionContext`, never from a second workspace field. Sanitize uploaded names to a basename, reject empty/unsupported names and files over 10 MiB, and use resolved-path containment for every read/write/download. Accept only `.txt`, `.md`, `.pdf`, `.docx`, and `.xlsx`; legacy `.doc`/`.xls` are explicitly unsupported. Treat the multipart content type as advisory and verify UTF-8 text, `%PDF` plus the page limit, or an OOXML ZIP containing `[Content_Types].xml` and the expected `word/document.xml` or `xl/workbook.xml`. Open XML archives with macros are rejected. Readers return bounded text (maximum 100,000 characters) and a clear truncation suffix. `.xlsx` returns sheet name, columns, up to 20 rows, and basic row/column counts without loading formulas or macros. Uploaded text is passed to the model only as delimited untrusted source material; prompts explicitly state that source instructions cannot alter tool permissions.

- [ ] **Step 3: Implement report generation**

Markdown writes atomically via a temporary sibling then rename. PDF uses ReportLab and `UnicodeCIDFont("STSong-Light")`; it renders headings, paragraphs, lists, and simple tables from Markdown without shelling out. Both formats are mandatory for Phase 2 tutorial closure. On PDF failure, Markdown remains, the runtime raises a redacted report-generation exception, and `TaskRegistry` emits the single `task_failed` terminal.

- [ ] **Step 4: GREEN and commit**

```bash
.venv/bin/python -m pytest tests/unit/phase2/test_context.py tests/unit/phase2/test_workspace.py tests/unit/phase2/test_file_reader.py tests/unit/phase2/test_reports.py -q
.venv/bin/ruff check app/api/context.py app/tools/files.py app/tools/reports.py tests/unit/phase2
.venv/bin/ruff format --check app/api/context.py app/tools/files.py app/tools/reports.py tests/unit/phase2
git diff --check
git add app/api/context.py app/tools/files.py app/tools/reports.py tests/unit/phase2/test_context.py tests/unit/phase2/test_workspace.py tests/unit/phase2/test_file_reader.py tests/unit/phase2/test_reports.py .gitignore docs/phase-status.md docs/verification/phase-2-evidence.md
git commit -m "feat: deliver tutorial report artifacts"
```

## Task 4: Assemble the Main Agent and Both Runtimes

**Files:**
- Create: `app/agent/factory.py`, `app/agent/runtime.py`
- Create: `tests/unit/phase2/test_agent_factory.py`, `test_runtime_events.py`
- Create: `tests/integration/phase2/test_mock_runtime.py`, `test_real_model_smoke.py`
- Modify: `docs/phase-status.md`, `docs/verification/phase-2-evidence.md`

**Interfaces:** Produces `create_tutorial_agent()`, `MockTutorialRuntime`, and `DeepAgentsTutorialRuntime` behind `TutorialRuntime`.

- [ ] **Step 1: Write RED factory/runtime tests**

Patch `create_deep_agent` and assert exact arguments: injected model; main prompt; file/report tools only at the main level; exactly three subagents; `InMemorySaver`; name `tutorial-research-agent`. Assert mock runtime calls all three providers from the injected bundle, consumes an uploaded Markdown fixture, creates both artifacts, emits paired agent/tool and artifact events, and emits no task lifecycle or terminal event.

```python
async def test_mock_runtime_completes_full_tutorial_flow(runtime, workspace, events):
    thread_id = "00000000-0000-4000-8000-000000000001"
    context = SessionContext(thread_id=thread_id, workspace=workspace)
    async with events.subscribe(thread_id) as subscription:
        result = await runtime.run(RuntimeRequest("compare sources", context))
        emitted = []
        while not subscription.queue.empty():
            emitted.append(subscription.queue.get_nowait())
    assert result.artifacts == ("tutorial-report.md", "tutorial-report.pdf")
    event_types = [event.type for event in emitted]
    assert "artifact_created" in event_types
    assert not {"task_started", "task_completed", "task_cancelled", "task_failed"} & set(event_types)
```

- [ ] **Step 2: Implement agent factory and real runtime**

`create_tutorial_agent()` is pure assembly and accepts model, `ProviderBundle`, `InMemoryEventBus`, and workspace factory. `DeepAgentsTutorialRuntime.run()` establishes `session_context(request.context)`, invokes `agent.astream(..., stream_mode="updates")` with `configurable.thread_id=request.context.thread_id`, obtains paths only from `request.context.workspace`, normalizes only agent/subagent/tool/result signals into agent/tool events, writes final reports through the report tools, and always resets context. It does not catch errors to translate them into task events: cancellation and all other exceptions propagate after context cleanup so `TaskRegistry` remains the sole terminal owner.

- [ ] **Step 3: Implement deterministic mock runtime**

Use the same injected `ProviderBundle`, event sink, and workspace interfaces. Execute one fixed sequence: Web search, list/preview/read-only catalog query, assistant discovery/question, optional uploaded-file read, Markdown, PDF. The report contains `web_mode`, `catalog_mode`, and `knowledge_mode`, and labels the result partially mocked when `ProviderBundle.uses_mock` is true.

- [ ] **Step 4: Add real-model smoke**

Gate with `PHASE2_REAL_MODEL_SMOKE=1` plus `MODEL_API_KEY`. Use mock Web/catalog/knowledge providers so the smoke measures only model/DeepAgents routing and artifact production. A real-model smoke must never silently switch to `MockTutorialRuntime`.

- [ ] **Step 5: GREEN and commit**

```bash
.venv/bin/python -m pytest tests/unit/phase2/test_agent_factory.py tests/unit/phase2/test_runtime_events.py tests/integration/phase2/test_mock_runtime.py -q
.venv/bin/python -m pytest tests/integration/phase2/test_real_model_smoke.py -q
.venv/bin/ruff check app/agent tests/unit/phase2 tests/integration/phase2
.venv/bin/ruff format --check app/agent tests/unit/phase2 tests/integration/phase2
git diff --check
git add app/agent/factory.py app/agent/runtime.py tests/unit/phase2/test_agent_factory.py tests/unit/phase2/test_runtime_events.py tests/integration/phase2/test_mock_runtime.py tests/integration/phase2/test_real_model_smoke.py docs/phase-status.md docs/verification/phase-2-evidence.md
git commit -m "feat: assemble tutorial deep agent runtime"
```

## Task 5: Close FastAPI, WebSocket, Upload, Cancellation, and Download

**Files:**
- Create: `app/api/schemas.py`, `app/api/tasks.py`, `app/api/server.py`
- Modify: `app/main.py`
- Create: `tests/unit/phase2/test_task_registry.py`
- Create: `tests/integration/phase2/test_api_contract.py`, `test_websocket_flow.py`
- Create: `tests/e2e/phase2/test_tutorial_closure.py`
- Modify: `docs/phase-status.md`, `docs/verification/phase-2-evidence.md`

**Interfaces:** Implements the locked HTTP/WebSocket contract. `app.main:create_app` remains the canonical app factory and `/health` reports `phase: "2"`, profile, runtime, and provider modes without secrets.

- [ ] **Step 1: Write RED contract tests**

Cover 202 task start, query validation, duplicate-running 409, isolated thread events/files, multipart upload, unsafe filenames, content-type/header mismatch, file listing, download containment, cancel 404, cancellation before runtime entry, active cancellation, runtime failure redaction, exactly one terminal per run, WebSocket subscription-before-start, ping/pong as a separate heartbeat shape, slow-subscriber close `1013`, and WebSocket terminal delivery. The e2e test must upload `constraints.md`, connect WebSocket and finish subscription setup, start a task with mock runtime/providers, collect events until terminal, assert all three provider tool names occurred, list both reports, download both, and verify Markdown contains uploaded constraints plus explicit provider modes.

- [ ] **Step 2: Implement in-memory registry and dependency wiring**

`TaskRegistry.start()` atomically rejects an active duplicate, creates one `SessionWorkspace` and one `SessionContext`, emits `task_started`, constructs `RuntimeRequest(query, context)`, creates an `asyncio.Task` around its private lifecycle runner, and removes it only when the same task finishes. The runner translates return/cancellation/error into exactly one terminal event and never exposes exception text, provider response bodies, paths, or credentials. `cancel()` calls `task.cancel()` and returns cancelled/cancelling with a one-second wait. App construction receives settings and optional `ProviderBundle`, runtime, and shared `InMemoryEventBus`; tests never mutate module globals.

The WebSocket handler enters `event_bus.subscribe(thread_id)` before accepting the socket, then races `subscription.queue.get()`, `subscription.overflowed.wait()`, and client messages: queued events are serialized as `TutorialEvent`; `{type:"ping"}` receives an immediate `{type:"pong"}` without entering the bus. Disconnect unregisters only that subscription and never cancels the task. An overflow signal closes that socket with `1013`. Phase 2 does not enumerate or replay the bus history to a new connection.

- [ ] **Step 3: Implement upload/list/download contracts**

Upload streams in chunks while enforcing 10 MiB per file. File listing enumerates only the thread output directory and returns sorted relative artifacts. Download accepts only a thread ID plus relative path and returns `FileResponse` after containment validation.

- [ ] **Step 4: GREEN and commit**

```bash
.venv/bin/python -m pytest tests/unit/phase2/test_task_registry.py tests/integration/phase2/test_api_contract.py tests/integration/phase2/test_websocket_flow.py tests/e2e/phase2/test_tutorial_closure.py -q
.venv/bin/python -m pytest tests/ -q
.venv/bin/ruff check app tests
.venv/bin/ruff format --check app tests
git diff --check
git add app/api/schemas.py app/api/tasks.py app/api/server.py app/main.py tests/unit/phase2/test_task_registry.py tests/integration/phase2/test_api_contract.py tests/integration/phase2/test_websocket_flow.py tests/e2e/phase2/test_tutorial_closure.py docs/phase-status.md docs/verification/phase-2-evidence.md
git commit -m "feat: close tutorial backend workflow"
```

## Task 6: Build the React Tutorial Workbench

**Files:**
- Modify: `.gitignore`
- Modify: `frontend/package.json`, `frontend/pnpm-lock.yaml`
- Create: `frontend/src/types.ts`, `frontend/src/lib/api.ts`, `frontend/src/hooks/useTutorialSession.ts`
- Create: `frontend/src/components/TaskComposer.tsx`, `RunStatus.tsx`, `EventFeed.tsx`, `ArtifactList.tsx`, `ReportPreview.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/App.test.tsx`, `frontend/src/app.css`
- Create: `frontend/src/hooks/useTutorialSession.test.ts`
- Create: `frontend/playwright.config.ts`, `frontend/e2e/tutorial-workbench.spec.ts`
- Modify: `docs/phase-status.md`, `docs/verification/phase-2-evidence.md`

**Interfaces:** Consumes only the locked HTTP and event contracts. Produces a work-focused single-screen UI with task input, upload, status/cancel, structured event feed, Markdown preview, and artifact downloads.

- [ ] **Step 1: Add dependencies and RED UI tests**

Add `react-markdown` and `lucide-react` to dependencies and `@playwright/test>=1.50,<2` to dev dependencies; regenerate only the frontend and root pnpm locks as required by the existing wrapper setup. Vitest/Testing Library tests assert query submission, upload before run, WebSocket URL construction, heartbeat handling outside the event feed, schema rejection, structured rendering for each event family, cancel visibility only while running, artifact refresh after completion, Markdown preview, download URL encoding, and error status. They do not claim to verify physical layout.

- [ ] **Step 2: Implement typed client and session hook**

`useTutorialSession` owns a UUID thread ID, awaits the WebSocket open handshake before POSTing the task, sends a ping heartbeat every 25 seconds, handles `HeartbeatMessage` separately, appends only schema-valid `TutorialEvent` objects, stops heartbeat on close/unmount, and refreshes artifacts after completed/failed/cancelled. It does not parse assistant prose to infer status and does not attempt replay after reconnect.

- [ ] **Step 3: Implement the workbench**

Use a restrained neutral work surface with a compact header, left task/actions column, central event feed, and right report/artifact column; collapse to one column on narrow screens. Use Lucide icons for upload, run, cancel, refresh, and download with accessible labels/tooltips. Keep cards at 8px radius or less, do not nest cards, and do not add Phase 3 controls such as strategy, budget, citations, approvals, or cost panels.

`frontend/playwright.config.ts` starts Vite on a dedicated test port and runs Chromium at desktop `1440x900` and mobile `390x844`. The Playwright test uses deterministic `page.route()` HTTP fixtures and `page.routeWebSocket()` terminal-event fixtures, loads the actual workbench, and at 390px asserts `document.documentElement.scrollWidth <= window.innerWidth`; task input, upload, run/cancel, event feed, preview, and download controls each have a non-zero bounding box fully inside the viewport. Add `frontend/test-results/` and `frontend/playwright-report/` to `.gitignore`; capture screenshots only there and never commit them.

- [ ] **Step 4: GREEN and commit**

```bash
pnpm --dir frontend exec vitest run
pnpm --dir frontend lint
pnpm --dir frontend build
pnpm --dir frontend exec playwright install chromium
pnpm --dir frontend exec playwright test
git diff --check
git add .gitignore frontend/package.json frontend/pnpm-lock.yaml pnpm-lock.yaml frontend/playwright.config.ts frontend/e2e/tutorial-workbench.spec.ts frontend/src/types.ts frontend/src/lib/api.ts frontend/src/hooks/useTutorialSession.ts frontend/src/hooks/useTutorialSession.test.ts frontend/src/components/TaskComposer.tsx frontend/src/components/RunStatus.tsx frontend/src/components/EventFeed.tsx frontend/src/components/ArtifactList.tsx frontend/src/components/ReportPreview.tsx frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/app.css docs/phase-status.md docs/verification/phase-2-evidence.md
git commit -m "feat: add tutorial research workbench"
```

## Task 7: Document, Verify, and Stop for Acceptance

**Files:**
- Create: `docs/phase-2-tutorial.md`
- Modify: `README.md`, `CHANGELOG.md`, `docs/phase-status.md`, `docs/verification/phase-2-evidence.md`
- Modify: `.github/workflows/ci.yml`

**Interfaces:** Produces reproducible tutorial chapter 8-14 evidence and the acceptance state. Does not create `v0.1-tutorial-parity`.

- [ ] **Step 1: Write the tutorial runbook and chapter matrix**

Document exact mock quick start, mixed-provider configuration, fresh-volume initialization and preserved-volume MySQL bootstrap, the SELECT-only account, external RAGFlow setup, Node 22 requirement, API request/response examples, heartbeat versus event shapes, live-only WebSocket semantics, artifact paths, cancellation semantics, real smoke opt-ins, and known limitations. Map chapters 8-14 to concrete files, tests, commands, and evidence rows.

Update CI so the Python job runs all offline Phase 2 tests without service/network dependencies and the Node 22 frontend job installs Playwright Chromium and runs both Vitest and Playwright. Compose MySQL integration remains a documented local/release gate unless CI explicitly adds a MySQL service and the same idempotent bootstrap command.

- [ ] **Step 2: Run the complete fresh gate**

```bash
git status --short
uv sync --extra dev --frozen
.venv/bin/python -m pytest tests/ -q
.venv/bin/ruff check app examples tests scripts
.venv/bin/ruff format --check app examples tests scripts
.venv/bin/pre-commit run --all-files
pnpm --dir frontend exec vitest run
pnpm --dir frontend lint
pnpm --dir frontend build
pnpm --dir frontend exec playwright install chromium
pnpm --dir frontend exec playwright test
docker compose config
docker compose up -d mysql
docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"' < docker/mysql/init/010_tutorial.sql
PHASE2_MYSQL_INTEGRATION=1 .venv/bin/python -m pytest tests/integration/phase2/test_mysql_provider.py -q
.venv/bin/python -m pytest tests/e2e/phase2/test_tutorial_closure.py -q
git diff --check
```

Record exact counts, exits, versions, skips, Compose port, and which provider/model smokes were not run. Stop and record a blocker on any required failure.

- [ ] **Step 3: Close docs and commit evidence**

Set Phase 2 status to `awaiting_user_acceptance`; mark Tasks 0-7 completed with real SHAs; state that the target tag has not been created and Phase 3 has not started. Update README/CHANGELOG only with verified behavior.

```bash
git add docs/phase-2-tutorial.md README.md CHANGELOG.md docs/phase-status.md docs/verification/phase-2-evidence.md .github/workflows/ci.yml
git diff --cached --name-only
git commit -m "docs: verify phase two tutorial parity"
```

The CI file is required in this commit because Playwright is a Phase 2 frontend acceptance gate.

- [ ] **Step 4: Final clean-state proof and stop**

```bash
git status --short
git diff --check
git tag --list v0.1-tutorial-parity
git log --oneline v0.0-deepagents-examples..HEAD
```

Expected: clean worktree; diff check passes; the target tag query has no output; only Phase 2 commits appear after the prerequisite tag. Report and stop. The user performs independent acceptance and separately authorizes tag creation.

## Required Stop Conditions

Stop the current task, update evidence with the command/error and attempted diagnosis, and request a decision when any of these occurs:

1. Installed DeepAgents/LangGraph signatures differ from ADR 0002 or require a version change.
2. A new dependency, service, route, event field, provider mode, database table, or frontend feature outside this plan appears necessary.
3. Safe read-only MySQL behavior cannot be enforced at both query validation and database-account levels.
4. A required implementation would expose absolute paths, credentials, uploaded content, or full provider responses in events.
5. Offline tests require a model, network, RAGFlow, or host MySQL.
6. Real adapter smoke fails after explicit opt-in; do not relabel it as skipped or mock-passed.
7. Node 22 is unavailable and the Node 22 CI gate also cannot be run.
8. Existing non-Phase-2 tests regress because of Phase 2 changes.
9. User changes overlap an allowed file and cannot be preserved safely.
10. Any work would begin Phase 3 or create `v0.1-tutorial-parity` before user acceptance.
11. The accepted plan/prompt cannot be tracked in Task 0 or the worktree cannot become clean without deleting user work.
12. Implementing live WebSocket delivery would require runtime-owned terminals, event history/replay, persistence, or a second event abstraction around the locked concrete bus.
13. The preserved MySQL volume cannot be bootstrapped idempotently, or the provider cannot connect and reject writes as `tutorial_reader`.

## Plan Self-Review

- Spec coverage: chapters 8-14 map to Tasks 0-7; tutorial profile, all three subagents, files/reports, API/WebSocket, React, isolation, cancellation, download, mocks, real smokes, docs, evidence, and tag gate each have an owner.
- Scope: evaluation datasets, citation verification, orchestration experiments, persistence/recovery, approvals, tracing/cost governance, and general Text-to-SQL are explicitly prohibited.
- Interface consistency: provider modes travel in `ProviderBundle`; runtimes emit only agent/tool/artifact events; `TaskRegistry` alone emits lifecycle terminals; one concrete `InMemoryEventBus` supplies live-only subscriptions without history; one `SessionContext` is shared by `RuntimeRequest` and `ContextVar`; heartbeat is outside the event union; artifact, HTTP, WebSocket, and frontend names are reused unchanged.
- Redundancy check: no hypothetical `EventSink`/`EventSource` seam, no `for_thread()` history accessor, no duplicate RuntimeRequest path fields, and no second ContextVar remain in the Phase 2 design.
- Environment consistency: the existing MySQL volume is preserved and explicitly bootstrapped; the application uses a SELECT-only account; Task 0 tracks both planning artifacts; Node 22 CI and real Chromium cover the responsive gate.
- Placeholder check: implementation decisions, commands, expected outcomes, commit boundaries, skips, and stop rules are explicit; no deferred design decision remains inside Phase 2.
