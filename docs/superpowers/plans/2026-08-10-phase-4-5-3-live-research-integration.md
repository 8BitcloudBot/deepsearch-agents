# P4.5-3 DeepAgents Live Research Integration Implementation Plan

> **Historical plan:** P4.5-3 is complete and this pre-migration plan is kept
> for audit. Its former provider-specific references are superseded by the
> Qdrant Local + FastEmbed migration design and are not execution guidance.

> **For the current Codex session:** REQUIRED SUB-SKILL: use
> `executing-plans` inline. Repository policy prohibits subagents, external
> coding workers and commits for this package.

**Goal:** Connect the explicit showcase profile to the existing DeepAgents
main-agent/expert-worker shape and return validated, deduplicated live source
evidence with honest partial-failure limitations.

**Architecture:** Add a dedicated showcase runtime around one injected agent
executor and one thread-scoped collector. Keep configuration, graph assembly
and provenance-recording source tools inside `app/showcase`; preserve offline,
tutorial, API, event, report and Phase 4 citation contracts.

**Tech Stack:** Python 3.12, dataclasses, Protocol, DeepAgents/LangGraph,
LangChain tools, existing Provider adapters, pytest and Ruff.

## Global Constraints

- Use only the current Codex session; do not dispatch subagents or other
  coding models.
- Do not call a real model, Provider, network or data source.
- Do not commit, push, tag, release or deploy.
- Do not modify API schemas, WebSocket event types, reports, frontend, Phase 4
  citation contracts or default tutorial/mock behavior.
- Missing opt-in, model or source configuration must fail closed without
  reading unrelated credentials or calling a source.
- P4.5-3 produces internal live sources/evidence/limitations only; P4.5-4
  delivery remains deferred.

---

## File Map

- Create `app/showcase/research.py`: live evidence, collector and runtime
  result value types.
- Create `app/showcase/config.py`: lazy showcase-only environment parsing and
  capability/config limitations.
- Create `app/showcase/runtime.py`: executor protocol and runtime behavior.
- Create `app/showcase/source_tools.py`: provenance-recording Web, MySQL,
  RAGFlow and uploaded-file tools.
- Create `app/showcase/agent.py`: dedicated DeepAgents graph assembly and
  executor adapter.
- Modify `app/providers/ragflow.py`: additive reference-preserving method.
- Modify `app/main.py`: assemble the showcase runtime.
- Modify `app/showcase/__init__.py`: export P4.5-3 types.
- Create `tests/unit/phase4_5/test_showcase_research.py`.
- Create `tests/unit/phase4_5/test_showcase_config.py`.
- Create `tests/unit/phase4_5/test_showcase_source_tools.py`.
- Create `tests/integration/phase4_5/__init__.py`.
- Create `tests/integration/phase4_5/test_showcase_runtime.py`.

### Task 1: Live evidence and collector module

**Files:**

- Create: `app/showcase/research.py`
- Test: `tests/unit/phase4_5/test_showcase_research.py`

**Interfaces:**

- Consumes: `SourceLocator`, `LocatorState`, `Limitation`, `SourceKind`,
  `validate_live_source_result` and `app.citations.rules.redact`.
- Produces:

```python
@dataclass(frozen=True)
class LiveEvidence:
    evidence_id: str
    source_id: str
    source_kind: SourceKind
    locator: dict[str, str]
    quote: str
    content_sha256: str
    thread_id: str | None

    def as_dict(self) -> dict[str, object]: ...


@dataclass(frozen=True)
class ShowcaseRunResult:
    answer: str
    artifacts: tuple[str, ...] = ()
    sources: tuple[SourceLocator, ...] = ()
    evidence: tuple[LiveEvidence, ...] = ()
    limitations: tuple[Limitation, ...] = ()


class LiveSourceCollector:
    def __init__(self, thread_id: str): ...
    def add(self, source: SourceLocator, *, quote: str) -> LiveEvidence: ...
    def add_limitation(self, limitation: Limitation) -> None: ...
    def snapshot(self, answer: str, artifacts: tuple[str, ...] = ()) -> ShowcaseRunResult: ...
```

- [ ] **Step 1: Write failing collector tests**

Add tests that build sources from the four existing P4.5-2 fixtures and prove:

```python
collector = LiveSourceCollector(THREAD_ID)
evidence = collector.add(source, quote=source.display_text)
result = collector.snapshot("done")

assert evidence.evidence_id.startswith("ev-live-")
assert result.sources == (source,)
assert result.evidence == (evidence,)
assert validate_live_source_result(source.as_live_source_result())
```

Also assert stable duplicate removal, first-seen ordering, JSON round-trip,
foreign-thread rejection, stale rejection, quote bounding/redaction and
limitation redaction.

- [ ] **Step 2: Verify RED**

Run:

```bash
UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run pytest \
  tests/unit/phase4_5/test_showcase_research.py -q
```

Expected: collection fails because `app.showcase.research` does not exist.

- [ ] **Step 3: Implement the minimal domain module**

Use canonical JSON with sorted keys for hashes. Compute:

```python
content_sha256 = sha256(normalized_quote.encode("utf-8")).hexdigest()
evidence_id = "ev-live-" + sha256(
    canonical_source_locator_and_quote.encode("utf-8")
).hexdigest()[:32]
```

Call `source.as_live_source_result(expected_thread_id=...)` before accepting a
source. Uploaded sources require the collector thread; other source kinds may
carry no thread. Reject non-valid states with `LocatorError`. Deduplicate
sources by `source_id` and evidence by `evidence_id`.

- [ ] **Step 4: Verify GREEN**

Run the Task 1 command and expect all tests to pass.

### Task 2: Fail-closed showcase configuration

**Files:**

- Create: `app/showcase/config.py`
- Test: `tests/unit/phase4_5/test_showcase_config.py`

**Interfaces:**

- Consumes: `resolve_capabilities(environ)` and existing environment names.
- Produces:

```python
@dataclass(frozen=True)
class ShowcaseRuntimeConfig:
    capabilities: ShowcaseCapabilities
    model_name: str
    model_base_url: str | None
    model_api_key: str | None
    web_provider: str | None
    tavily_api_key: str | None
    catalog_provider: str | None
    mysql_host: str | None
    mysql_port: int | None
    mysql_user: str | None
    mysql_password: str | None
    mysql_database: str | None
    knowledge_provider: str | None
    ragflow_base_url: str | None
    ragflow_api_key: str | None
    limitations: tuple[Limitation, ...]

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> "ShowcaseRuntimeConfig": ...

    @property
    def model_available(self) -> bool: ...
```

- [ ] **Step 1: Write failing configuration tests**

Use a guarded mapping whose `get()` raises for model/Provider credential keys.
Prove no credential key is read when opt-in is absent. With exact opt-in,
prove only declared-source credentials are read. Pin these outcomes:

```python
assert config.model_available is False
assert any(l.code == "model-unavailable" for l in config.limitations)
assert config.capabilities.check("web").enabled is True
assert config.tavily_api_key is None
```

Invalid provider mode, port, missing credential or non-read-only MySQL user
must yield a redacted per-source limitation instead of raising or constructing
an adapter.

- [ ] **Step 2: Verify RED**

Run:

```bash
UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run pytest \
  tests/unit/phase4_5/test_showcase_config.py -q
```

Expected: missing-module failure.

- [ ] **Step 3: Implement minimal lazy parsing**

Resolve opt-in and declarations first. Return immediately with capability
limitations when disabled. Under exact opt-in, read model configuration, then
read Tavily/MySQL/RAGFlow credentials only when that source is declared.
Uploaded files require no credential. Never place credential values in a
limitation message.

- [ ] **Step 4: Verify GREEN**

Run the Task 2 command and expect all tests to pass.

### Task 3: Runtime and executor seam

**Files:**

- Create: `app/showcase/runtime.py`
- Test: `tests/integration/phase4_5/__init__.py`
- Test: `tests/integration/phase4_5/test_showcase_runtime.py`

**Interfaces:**

- Consumes: `RuntimeRequest`, `InMemoryEventBus`, `session_context`,
  `LiveSourceCollector`, `ShowcaseRunResult` and configuration limitations.
- Produces:

```python
class ShowcaseAgentExecutor(Protocol):
    async def run(
        self,
        request: RuntimeRequest,
        collector: LiveSourceCollector,
    ) -> str: ...


class ShowcaseResearchRuntime:
    def __init__(
        self,
        events: InMemoryEventBus,
        executor: ShowcaseAgentExecutor | None,
        limitations: tuple[Limitation, ...] = (),
    ): ...

    async def run(self, request: RuntimeRequest) -> ShowcaseRunResult: ...
```

- [ ] **Step 1: Write failing runtime tests with deterministic executors**

Create an executor that records all four fixture-derived sources, one that
raises a raw secret/path error and a spy that must not be called. Assert:

```python
result = await runtime.run(request)
assert len(result.sources) == 4
assert len(result.evidence) == 4
assert result.artifacts == ()
assert executor.calls == 1
```

For `executor=None`, assert zero source calls and a structured limitation.
For executor failure, assert `agent-failed`, no raw secret/path, and no
runtime-owned task terminal event. Run the runtime through `TaskRegistry` and
assert exactly one terminal event from the registry.

- [ ] **Step 2: Verify RED**

Run:

```bash
UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run pytest \
  tests/integration/phase4_5/test_showcase_runtime.py -q
```

Expected: missing runtime module or interface failure.

- [ ] **Step 3: Implement minimal runtime**

Enter `session_context`, create one collector for the request thread, add
preflight limitations, and skip executor invocation when it is `None`. Emit
only existing `agent_started` and `agent_completed` events. Catch executor
exceptions, add generic redacted `agent-failed`, and return a snapshot rather
than leaking the exception.

- [ ] **Step 4: Verify GREEN**

Run the Task 3 command and expect all tests to pass.

### Task 4: Provenance-recording source tools

**Files:**

- Create: `app/showcase/source_tools.py`
- Modify: `app/providers/ragflow.py`
- Test: `tests/unit/phase4_5/test_showcase_source_tools.py`

**Interfaces:**

- Consumes: existing Provider methods, P4.5-2 normalization functions,
  `LiveSourceCollector`, `RunnableConfig` and current session workspace.
- Produces:

```python
@dataclass(frozen=True)
class ShowcaseProviders:
    web: WebSearchProvider | None = None
    catalog: CatalogProvider | None = None
    knowledge: object | None = None


def create_showcase_source_tools(
    providers: ShowcaseProviders,
    events: InMemoryEventBus,
    collector: LiveSourceCollector,
    *,
    captured_at: Callable[[], str],
) -> ShowcaseToolSet: ...
```

`ShowcaseToolSet` contains main uploaded-file tools plus Web, catalog and
knowledge expert-tool lists. Disabled providers produce no callable tool.

The concrete RAGFlow adapter adds:

```python
def ask_with_references(
    self, assistant_name: str, question: str
) -> tuple[KnowledgeAnswer, tuple[dict[str, object], ...]]: ...
```

- [ ] **Step 1: Write failing tool tests**

Use deterministic fake Providers and direct LangChain tool invocation. Prove
Web hits, MySQL row/column cells, RAGFlow chunks and uploaded line spans record
valid sources/evidence. Assert provider failures become `source-failed`
limitations while another tool remains usable. Assert RAGFlow references
without any one required ID produce no evidence and a `missing-source`
limitation.

For MySQL, pin `id` as preferred row identity and this fallback:

```python
row_identity = "row-" + sha256(canonical_row_json).hexdigest()[:16]
```

- [ ] **Step 2: Verify RED**

Run:

```bash
UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run pytest \
  tests/unit/phase4_5/test_showcase_source_tools.py -q
```

Expected: missing source-tools module failure.

- [ ] **Step 3: Implement source tools and RAGFlow reference preservation**

Each tool owns its existing `tool_started`/`tool_completed` events. On source
failure, record a generic limitation and return a bounded unavailable string;
do not emit `tool_completed` for failed calls. Never serialize raw response
objects. The RAGFlow method reads `Message.reference` only and returns copied
reference mappings; existing `ask()` behavior and protocol remain intact.

- [ ] **Step 4: Verify GREEN**

Run the Task 4 command and the existing focused provider/tool regressions:

```bash
UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run pytest \
  tests/unit/phase4_5/test_showcase_source_tools.py \
  tests/unit/phase2/test_tool_events.py \
  tests/unit/phase2/test_provider_factories.py -q
```

### Task 5: DeepAgents executor and application wiring

**Files:**

- Create: `app/showcase/agent.py`
- Modify: `app/main.py`
- Modify: `app/showcase/__init__.py`
- Test: `tests/integration/phase4_5/test_showcase_runtime.py`

**Interfaces:**

- Consumes: `ShowcaseRuntimeConfig`, `ShowcaseProviders`, source tool set,
  existing main prompt security invariant and `deepagents.create_deep_agent`.
- Produces:

```python
class DeepAgentsShowcaseExecutor:
    async def run(
        self,
        request: RuntimeRequest,
        collector: LiveSourceCollector,
    ) -> str: ...


def build_showcase_runtime(
    *,
    environ: Mapping[str, str],
    events: InMemoryEventBus,
) -> ShowcaseResearchRuntime: ...
```

- [ ] **Step 1: Extend failing integration tests**

Patch model and Provider constructors with spies/fakes. Assert:

- no opt-in: app starts and no model/Provider constructor is called;
- opt-in but missing model: app starts and no Provider constructor is called;
- opt-in with configured fake model and partial sources: only declared,
  configured adapters are constructed;
- graph assembly has only the existing coordinator plus Web,
  structured-data and knowledge-base expert roles;
- default tutorial and agent-research assembly remain unchanged.

- [ ] **Step 2: Verify RED**

Run the specific new integration tests and confirm they fail because showcase
still uses `AgentResearchRuntime`.

- [ ] **Step 3: Implement graph and main wiring**

Build subagent dictionaries from available source tool lists. Keep the
uploaded tool at main level. `DeepAgentsShowcaseExecutor` mirrors the accepted
`DeepAgentsTutorialRuntime` stream handling but does not generate reports or
artifacts. `build_showcase_runtime` constructs lazy concrete adapters only
after all relevant gates pass. Change only the showcase branch in
`app.main.create_app()`.

- [ ] **Step 4: Verify GREEN and nearby regressions**

Run:

```bash
UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run pytest \
  tests/integration/phase4_5/test_showcase_runtime.py \
  tests/unit/phase3/test_research_profile.py \
  tests/unit/phase4_5/test_showcase_contracts.py \
  tests/unit/phase4_5/test_source_locators.py -q
```

### Task 6: Package verification

**Files:** No production changes unless a focused gate exposes a P4.5-3 defect.

- [ ] **Step 1: Run the affected backend regression surface**

```bash
UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run pytest \
  tests/unit/phase4_5 \
  tests/integration/phase4_5 \
  tests/unit/phase3/test_research_profile.py \
  tests/unit/phase2/test_runtime_events.py \
  tests/unit/phase2/test_tool_events.py \
  tests/unit/phase2/test_provider_factories.py \
  tests/integration/phase3/test_research_runtime.py \
  tests/unit/phase4/test_citation_contracts.py -q
```

- [ ] **Step 2: Run touched-file static checks**

```bash
UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run ruff check \
  app/showcase app/main.py app/providers/ragflow.py \
  tests/unit/phase4_5 tests/integration/phase4_5

UV_CACHE_DIR=/tmp/deepsearch-uv-cache uv run ruff format --check \
  app/showcase app/main.py app/providers/ragflow.py \
  tests/unit/phase4_5 tests/integration/phase4_5

git diff --check
```

- [ ] **Step 3: Confirm scope and safety**

Inspect `git status --short` and the P4.5-3 diff. Confirm no API, WebSocket,
report, frontend, Phase 4 citation contract, remote Git state or pre-existing
user documentation change was modified by implementation.

## Self-Review

- Every approved design requirement maps to Tasks 1-5.
- Type names and method signatures are consistent across tasks.
- No task requires a real model, Provider, network or data source.
- P4.5-4 delivery and all later packages remain explicitly excluded.
- The verification surface distinguishes collector, tool, runtime, assembly
  and legacy-regression failure modes without running the full suite.
# Historical Plan Notice

This completed package record documents the former provider-specific implementation.
It was superseded by
`docs/superpowers/specs/2026-08-10-knowledge-retrieval-qdrant-local-fastembed-migration-design.md`
and is not current execution guidance. References below to the original tutorial
provider are retained only as historical facts.
