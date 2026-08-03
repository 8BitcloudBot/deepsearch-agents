# Phase 2 Tutorial — 教程基线 Runbook（第 8–14 章）

> 本文是 Phase 2（Tutorial Parity）的可复现操作手册：离线 mock 快速启动、混合
> Provider 配置、受控 MySQL 引导、外部 RAGFlow/真实模型 opt-in、API 与
> WebSocket 契约示例、以及教程第 8–14 章到代码/测试/命令/证据的映射矩阵。
>
> 基线来源：教程 upstream 提交
> `didilili/deepsearch-agents@d0f6eed1e14b1b457942ba2a0195f65731aaf444`
> 仅用于行为对照；本项目代码、测试与文档独立实现。验收证据见
> [`docs/verification/phase-2-evidence.md`](verification/phase-2-evidence.md)，
> 当前状态见 [`docs/phase-status.md`](phase-status.md)。

## 1. 环境要求

| 依赖 | 版本要求 | 说明 |
|---|---|---|
| Python | 3.12（`pyproject.toml` 锁定 `>=3.12,<3.13`） | 由 `uv` 自动安装管理版本 |
| Node.js | **22**（前端发布门禁） | CI 的 frontend job 固定 `node-version: 22`；本地机器若不是 22，见 §10 限制 |
| pnpm | 10 | 通过 `corepack` 或 `pnpm/action-setup` 提供 |
| uv | 最新 | 项目依赖锁定在 `uv.lock`，一律 `--frozen` |
| Docker + Docker Compose | 任意较新版本 | 仅 MySQL 集成门禁需要 |

锁定版本（ADR 0003 实测）：`deepagents==0.6.12`、`langgraph==1.2.9`、
`langchain-core==1.5.1`、`langchain-openai==1.4.1`、`tavily-python==0.7.26`、
`ragflow-sdk==0.26.0`、`sqlglot==29.0.1`、`pypdf==6.14.2`、
`python-docx==1.2.0`、`openpyxl==3.1.5`、`reportlab==4.5.1`、`httpx==0.28.1`。

## 2. 离线 mock 快速启动（无需任何 Key / 网络）

默认环境全部是 mock：`TUTORIAL_RUNTIME=mock`、`WEB_PROVIDER=mock`、
`CATALOG_PROVIDER=mock`、`KNOWLEDGE_PROVIDER=mock`（`app/settings.py` 默认值），
因此**不需要模型 Key、Tavily Key、RAGFlow 或 MySQL**。

```bash
# 1) 后端依赖（首次运行；.venv 会被创建且已被 .gitignore 忽略）
uv sync --extra dev --frozen

# 2) 启动后端 API（mock runtime + 三个 mock provider）
uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000

# 3) 前端依赖与开发服务器（另一个终端）
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend dev          # http://127.0.0.1:5173
```

健康检查（无密钥泄露，报告 profile/runtime/provider 模式）：

```bash
curl -s http://127.0.0.1:8000/health
```

```json
{
  "status": "ok",
  "service": "research-copilot-api",
  "phase": "2",
  "tutorial_profile": "tutorial",
  "tutorial_runtime": "mock",
  "web_provider": "mock",
  "catalog_provider": "mock",
  "knowledge_provider": "mock"
}
```

在浏览器打开 `http://127.0.0.1:5173`：输入问题（如 `research aspirin`），
可选上传约束文件，点击 Run。前端先建立 `WS /ws/{thread_id}`，再 `POST /api/task`，
事件流实时渲染，任务结束后可预览/下载 `tutorial-report.md` 与
`tutorial-report.pdf`。

mock 模式下报告会带有 `> ⚠️ Partially mocked — at least one provider is in mock mode.`
横幅，明确区分 mock 与真实服务结果。

## 3. Provider 选择与混合配置

三个外部依赖各自独立选择，模式与实现一起封装在不可变的
`ProviderBundle`（`app/providers/contracts.py`）；provenance 只来自显式 mode
字段，从不通过 `isinstance()` 推断。真实适配器是惰性构造的（只在
`build_providers(settings)` 里按需 import/构造），模块 import 不产生任何外部连接。

| 变量 | 可选值 | 默认 | 真实模式额外要求 |
|---|---|---|---|
| `TUTORIAL_RUNTIME` | `mock` \| `deepagents` | `mock` | `deepagents` 需要 `MODEL_API_KEY`（否则启动即报错） |
| `WEB_PROVIDER` | `mock` \| `tavily` | `mock` | `TAVILY_API_KEY` |
| `CATALOG_PROVIDER` | `mock` \| `mysql` | `mock` | `MYSQL_USER` 必须是 `tutorial_reader`（工厂强制） |
| `KNOWLEDGE_PROVIDER` | `mock` \| `ragflow` | `mock` | `RAGFLOW_API_KEY` + `RAGFLOW_BASE_URL` |

混合配置示例（真实 Web + 真实 MySQL + mock Knowledge）：

```bash
WEB_PROVIDER=tavily \
CATALOG_PROVIDER=mysql \
KNOWLEDGE_PROVIDER=mock \
TAVILY_API_KEY=... \
MYSQL_HOST=127.0.0.1 MYSQL_PORT=3307 \
uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

非法值会在启动时以 `ValueError` 失败（如 `WEB_PROVIDER=foo`），不会静默回退。
`/health` 会如实显示每个 mode；报告中的 `## Provider Modes` 节同样按 mode 字段
输出，mock 模式绝不冒充真实服务成功。

## 4. 受控 MySQL：全新卷与保留卷引导

### 4.1 架构与安全

- 两层只读防御（全局约束 23 条）：
  1. `sqlglot`（MySQL dialect）解析并遍历 AST，只接受**单条**只读 `SELECT`
     或 `WITH ... SELECT`；拒绝 DDL/DML/`CALL`/`LOAD_FILE`/`INTO OUTFILE`/
     注释/多语句/跨库 `other_db.table`；
  2. 应用以 **`tutorial_reader`** 账号连接，该账号对 `research_copilot.*`
     仅有 `SELECT`，无任何写权限。
- 真实查询附加 `MAX_EXECUTION_TIME(5000)`，并包成
  `SELECT * FROM (<accepted query>) AS phase2_query LIMIT <limit>`（上限 100），
  已有 `LIMIT` 无法绕过上限（`app/providers/mysql.py`）。
- root 账号只用于引导（bootstrap），Provider 永不使用。

### 4.2 全新数据卷（首次启动）

Compose 挂载 `./docker/mysql/init:/docker-entrypoint-initdb.d:ro`，
MySQL 8.0 首次初始化新数据目录时**自动**执行
`docker/mysql/init/010_tutorial.sql`（建表 + 种子 + 授权）：

```bash
docker compose up -d mysql
```

### 4.3 保留数据卷（已有 mysql_data，必须显式引导）

Docker 的 init 脚本**只在数据目录首次创建时运行**。为了保留既有卷
（Phase 0/1 以来的 `mysql_data`），每次需要时**显式引导**，且脚本本身幂等
（`START TRANSACTION` 内重建三张表与种子；`CREATE USER IF NOT EXISTS` +
`ALTER USER` 重设 `tutorial_reader`；`REVOKE ALL` + `GRANT SELECT` +
`FLUSH PRIVILEGES`）：

```bash
docker compose up -d mysql

# 保留卷缺少 research_copilot 数据库时（例如数据目录早于 MYSQL_DATABASE
# 配置创建，本机验收即此情况），先用 root 一次性创建，非破坏性：
docker compose exec -T mysql sh -c 'mysql -uroot -proot -e "CREATE DATABASE IF NOT EXISTS research_copilot"'

# 幂等引导：对既有卷重复执行是安全的（本机连续执行 3 次均 exit 0）
docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"' < docker/mysql/init/010_tutorial.sql

# 以 SELECT-only 账号验证（SELECT 通过；INSERT 被拒：ERROR 1142）
docker compose exec -T mysql sh -c 'mysql -ututorial_reader -ptutorial_reader "$MYSQL_DATABASE" -e "SELECT COUNT(*) FROM drugs"'
```

> 禁止 `docker compose down -v` 或删除/重建现有卷。

### 4.4 表结构与种子

`drugs`（`id,name,category,price`）、`inventory`（`drug_id,quantity,warehouse`）、
`sales_records`（`id,drug_id,sale_date,amount`）。种子：Aspirin/Ibuprofen/
Paracetamol 三行药品、两个仓库库存、三行销售记录。

### 4.5 启用真实 Catalog Provider 与集成门禁

```bash
# 应用侧（tutorial_reader 是强制账号）
CATALOG_PROVIDER=mysql MYSQL_HOST=127.0.0.1 MYSQL_PORT=3307 \
  MYSQL_USER=tutorial_reader MYSQL_PASSWORD=tutorial_reader \
  MYSQL_DATABASE=research_copilot \
  uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000

# 本地集成门禁（默认跳过；显式开启）
PHASE2_MYSQL_INTEGRATION=1 .venv/bin/python -m pytest tests/integration/phase2/test_mysql_provider.py -q
```

该集成测试断言：表发现、schema、preview、join/聚合 SELECT、截断，以及
`tutorial_reader` 直接 `INSERT` 被 MySQL 拒绝且行数不变。Compose MySQL
集成是**本地/release 门禁**，CI 的 Python job 不启动 MySQL 服务。

## 5. 外部服务与真实模型 opt-in（各自独立、显式标号）

以下 smoke 全部**默认跳过**，且“配置缺失”是 honest skip，不是成功；
“配置了但失败”是失败，绝不把 mock 结果上报为真实服务成功。

### 5.1 Tavily（真实 Web）

```bash
WEB_PROVIDER=tavily TAVILY_API_KEY=... uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
PHASE2_TAVILY_SMOKE=1 .venv/bin/python -m pytest tests/integration/phase2/test_external_provider_smoke.py -q
```

### 5.2 RAGFlow（外部部署的 Knowledge 服务）

RAGFlow 不在本仓库 Compose 范围内，需要**自行外部部署**
（官方 docker 部署，服务地址如 `http://<ragflow-host>:9380`），并准备
API Key。SDK 表面按 ADR 0003 实测：`RAGFlow(api_key, base_url, version='v1')`
提供 `list_chats` / `create_chat` / `delete_chats` / `get_recent_messages`；
Provider 每次 `ask` 创建临时 chat、`finally` 中删除，回答映射为
`KnowledgeAnswer`（`app/providers/ragflow.py`）。

```bash
KNOWLEDGE_PROVIDER=ragflow RAGFLOW_BASE_URL=http://127.0.0.1:9380 RAGFLOW_API_KEY=... \
  uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
PHASE2_RAGFLOW_SMOKE=1 .venv/bin/python -m pytest tests/integration/phase2/test_external_provider_smoke.py -q
```

### 5.3 真实模型 / DeepAgents runtime

`TUTORIAL_RUNTIME=deepagents` 使用 OpenAI-compatible 模型（`ChatOpenAI`）。
需要 `MODEL_API_KEY`（缺失时 `create_app()` 直接 `RuntimeError`）；可选
`MODEL_NAME`（默认 `openai:gpt-4.1-mini`）与 `MODEL_BASE_URL`。模型 smoke
用 mock Web/Catalog/Knowledge，只度量模型/DeepAgents 路由与报告产出：

```bash
TUTORIAL_RUNTIME=deepagents MODEL_API_KEY=... uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
PHASE2_REAL_MODEL_SMOKE=1 .venv/bin/python -m pytest tests/integration/phase2/test_real_model_smoke.py -q
```

## 6. HTTP API 契约（实测示例）

基线路径固定：`POST /api/task`、`POST /api/task/{thread_id}/cancel`、
`POST /api/upload`、`GET /api/files`、`GET /api/download`、`WS /ws/{thread_id}`。

### 6.1 启动任务

```bash
TID=$(uuidgen | tr 'A-Z' 'a-z')   # 任意 UUID；也可省略让服务端生成
curl -s -X POST http://127.0.0.1:8000/api/task \
  -H 'Content-Type: application/json' \
  -d "{\"query\":\"research aspirin\",\"thread_id\":\"$TID\"}"
```

- `202` → `{"status":"started","thread_id":"<uuid>"}`
- `422`：query 为空 / `thread_id` 不是 UUID（Pydantic 校验失败）
- `409`：同一 `thread_id` 已有运行中的任务（`DuplicateTaskError`）

### 6.2 上传约束文件

```bash
curl -s -X POST http://127.0.0.1:8000/api/upload \
  -F thread_id="$TID" -F files=@constraints.md
```

- `200` → `{"status":"uploaded","thread_id":"<uuid>","files":[{"name":"constraints.md","size":12}]}`
- 允许扩展名：`.txt` `.md` `.pdf` `.docx` `.xlsx`；单文件上限 **10 MiB**
  （`413`）；非法文件名/伪造内容 `400`。上传目录：
  `updated/session_<thread_id>/`（相对进程 CWD）。

### 6.3 取消任务

```bash
curl -s -X POST http://127.0.0.1:8000/api/task/$TID/cancel
```

- `200` → `{"status":"cancelled"|"cancelling","thread_id":"<uuid>"}`
  （取消成功返回 `cancelled`；超过 1 秒等待仍未终止返回 `cancelling`）
- `404` → `{"detail":"task not found"}`（无活跃任务）

### 6.4 列出与下载产物

```bash
curl -s "http://127.0.0.1:8000/api/files?thread_id=$TID"
curl -s -o tutorial-report.md "http://127.0.0.1:8000/api/download?thread_id=$TID&path=tutorial-report.md"
curl -s -o tutorial-report.pdf "http://127.0.0.1:8000/api/download?thread_id=$TID&path=tutorial-report.pdf"
```

- `GET /api/files` → `{"thread_id":"<uuid>","files":[{"name":"tutorial-report.md","path":"tutorial-report.md","size":N,"media_type":"text/markdown"},{"name":"tutorial-report.pdf","path":"tutorial-report.pdf","size":N,"media_type":"application/pdf"}]}`
- `GET /api/download`：`400` 非法路径（containment 校验）、`404` 文件不存在。
  产物目录：`output/session_<thread_id>/`；`path` 始终是相对路径，客户端不接触
  任何绝对服务器路径。

## 7. WebSocket 契约（`WS /ws/{thread_id}`）

### 7.1 连接即订阅：live-only，无回放

服务端在 `accept()` 之前完成 `InMemoryEventBus.subscribe(thread_id)` 注册，
因此**先连 WS、再启动任务**不会漏事件。连接只收到**订阅之后**发出的事件；
Phase 2 不保存历史、不支持 replay/重连补发（属 Phase 7）。断线只注销该订阅，
**不取消任务**；任务在服务端内存中继续执行直到终态。

### 7.2 事件顺序（mock runtime 实测全量 26 条，sequence 从 1 递增）

`sequence` 按 thread 单调递增（同一连接不会重号）；`task_started` 由
`TaskRegistry` 同步发出，终态事件（completed/cancelled/failed）**恰好一个**，
由 registry 独占；runtime 只发 `agent_*` / `tool_*` / `artifact_created`。

| seq | type | message / data |
|---|---|---|
| 1 | `task_started` | message=query, `data={}` |
| 2 | `agent_started` | `agent_name: "mock-research-agent"` |
| 3-4 | `tool_started` / `tool_completed` | `internet_search` |
| 5-6 | `tool_started` / `tool_completed` | `list_sql_tables` |
| 7-12 | `tool_started` / `tool_completed` ×3 | `preview_table`（drugs、inventory、sales_records） |
| 13-14 | `tool_started` / `tool_completed` | `execute_readonly_query` |
| 15-16 | `tool_started` / `tool_completed` | `list_knowledge_assistants` |
| 17-18 | `tool_started` / `tool_completed` | `ask_knowledge_assistant` |
| 19-22 | `tool_started` / `tool_completed` ×2 | `generate_markdown_report`、`generate_pdf_report` |
| 23-24 | `artifact_created` ×2 | `tutorial-report.md`（`text/markdown`）、`tutorial-report.pdf`（`application/pdf`） |
| 25 | `agent_completed` | `agent_name: "mock-research-agent"` |
| 26 | `task_completed` | message=空, `data={}` |

单条事件 JSON（实测序列化形状，UTC ISO-8601）：

```json
{
  "version": 1,
  "sequence": 1,
  "thread_id": "57dc7cb9-72cf-44ab-8194-b09c93d579fb",
  "type": "task_started",
  "message": "research aspirin",
  "data": {},
  "timestamp": "2026-08-03T11:13:59.459680Z"
}
```

约束：`data` 必须是严格 JSON（`bytes`/`set`/`tuple`/非字符串键被拒绝）；
事件永不含 token、成本、trace ID、持久化 ID、replay cursor、审批字段；
`tool_*` 带 `tool_name`，`agent_*` 带 `agent_name`，`artifact_created` 带
`path`/`name`/`media_type`。

### 7.3 heartbeat 与 TutorialEvent 是两种不同形状

客户端心跳 `{"type":"ping"}` 的应答是独立心跳消息，**不是** `TutorialEvent`：

```json
{"type":"pong"}
```

`pong` 没有 `sequence`、不进入事件总线、不计入事件序号、不存储。前端
`useTutorialSession` 在 socket 打开期间每 **25 秒**发送一次 ping
（`HEARTBEAT_INTERVAL_MS = 25_000`），收到 `pong` 直接丢弃，不渲染进事件流。

### 7.4 慢订阅者溢出

每个订阅是**有界队列（256 条）**。生产者（任务侧）从不阻塞：队列满时该订阅
被移除并置位 `overflowed`，服务端以 WebSocket **close code 1013** 关闭该连接；
不影响任务继续执行和其他订阅者。

## 8. 取消语义

- `POST /api/task/{thread_id}/cancel` 调用 `asyncio.Task.cancel()` 并最多等待 1 秒；
  `cancelled`（已终止）或 `cancelling`（仍在收尾）；registry 随即清理。
- 进入 runtime 之前被取消（pre-entry cancel）：registry 自己补发
  `task_cancelled` 终态，不向调用方泄漏 `CancelledError`。
- 取消/失败/成功都只产生**恰好一个**终态事件；异常文本、Provider 原始响应、
  路径与凭据永不出现在事件中（脱敏后统一 `task_failed`）。
- WebSocket 断线不取消任务；UI 上取消是独立的 HTTP 调用。

## 9. 前端 Workbench

- `frontend/src/hooks/useTutorialSession.ts`：每次会话铸造一个 UUID thread；
  `run()` 先开 WS（`ws://127.0.0.1:8000/ws/{thread_id}`，https 自动转 wss），
  open 之后才 POST `/api/task`；只追加通过严格 schema 校验的 `TutorialEvent`；
  终态后刷新 `/api/files` 并关闭 socket。
- 组件：`TaskComposer`（输入+上传）、`RunStatus`（状态+取消）、`EventFeed`
  （结构化事件）、`ArtifactList`（下载）、`ReportPreview`（Markdown 预览）。
- Playwright（`frontend/playwright.config.ts`）：Vite 专用端口 5173，Chromium
  desktop `1440x900` 与 mobile `390x844` 两个 project；测试用
  `page.route()` / `page.routeWebSocket()` 的确定性 fixture 驱动真实 UI，
  **不启动后端进程**；390px 断言 `scrollWidth <= innerWidth` 且每个控件
  bounding box 都在视口内。

## 10. 已知限制（Phase 2 边界）

1. **任务与事件仅存内存**：进程重启即丢失；无持久化、无断线续传、无服务重启
   恢复（Phase 7）。
2. **live-only**：连接只收到订阅后的事件；无 replay 光标、无历史枚举（Phase 7）。
3. **慢订阅者**：256 条有界队列，溢出以 1013 关闭，不阻塞任务。
4. **上传**：仅 `.txt/.md/.pdf/.docx/.xlsx`，单文件 ≤ 10 MiB。
5. **数据库**：只读 SELECT（sqlglot AST + `tutorial_reader` 账号双层）；
   无 DDL/DML；`MYSQL_USER` 必须为 `tutorial_reader`。
6. **mock 语义**：mock Web 结果是两条固定 fixture；mock Knowledge 是固定答案；
   报告含 “Partially mocked” 横幅；mock 成功绝不当作真实服务成功。
7. **外部 smoke 默认跳过**：Tavily/RAGFlow/真实模型均需显式 opt-in 与凭据。
8. **RAGFlow 不在 Compose 内**：需要自行外部部署（§5.2）。
9. **Phase 3+ 不做**：评测数据、引用验证、策略实验、trace/成本治理、持久化
   任务/事件/checkpoint、审批——均不属于 Phase 2（全局约束 15 条）。
10. **Node 22 门禁**：前端 release 门禁要求 Node 22；本机非 Node 22 时记录在
    证据中，Node 22 CI job（§11）是验收前必须执行的 gate。
11. **真实 runtime 报告**：`DeepAgentsTutorialRuntime` 依赖模型实际调用报告
    tool；未生成时会以收集到的回答文本补偿生成两份报告，并补发
    `artifact_created`（不重复 tool 事件）。

## 11. CI 门禁（`.github/workflows/ci.yml`）

- **python**（ubuntu-latest, Python 3.12）：`uv sync --extra dev --frozen` →
  `pytest tests/ -q`（全部离线 Phase 2 测试，无服务/网络依赖）→
  `ruff check` → `ruff format --check` → `pre-commit run --all-files` →
  `docker compose config` → `doctor.py --offline`。**不启动 MySQL**；
  Compose MySQL 集成是文档化的本地/release 门禁（§4.5）。
- **frontend**（ubuntu-latest, **Node 22**）：`pnpm install --frozen-lockfile`
  → `playwright install --with-deps chromium` → `vitest run` → `lint` → `build`
  → `playwright test`（Chromium desktop + mobile）。

## 12. 教程第 8–14 章映射矩阵

| 章 | 教程内容 | 对应文件/模块 | 测试 | 命令 | 证据 |
|---|---|---|---|---|---|
| 8 | 项目目标、架构、目录 | `docs/phases/phase-2-tutorial-parity.md`、`docs/adr/0003-…-contracts.md`、`app/`、`frontend/` | `test_settings.py`（profile 契约） | 本文 §2 快速启动 | 证据 Task 0（`6a5d15a`） |
| 9 | 工程底座（context/monitor/llm/prompts） | `app/api/context.py`、`app/api/events.py`、`app/settings.py`、`app/agent/prompts.py`、`app/agent/subagents.py` | `tests/unit/phase2/test_context.py`、`test_events.py`、`test_settings.py`、`test_subagents.py` | `uv run pytest tests/unit/phase2 -q` | 证据 Task 1 |
| 10 | 网络搜索助手（Web/Tavily） | `app/providers/tavily.py`、`app/providers/mock.py`（`MockWebProvider`）、`app/tools/web.py` | `test_external_adapters.py`、`test_tool_events.py`、`test_mock_providers.py`、`test_external_provider_smoke.py`（`PHASE2_TAVILY_SMOKE=1`） | 同上 + §5.1 | 证据 Task 2；E2E 断言 `internet_search` 事件 |
| 11 | 数据库查询助手（MySQL） | `app/providers/mysql.py`、`app/tools/catalog.py`、`docker/mysql/init/010_tutorial.sql`、`docker-compose.yml` | `test_sql_policy.py`、`test_mysql_provider.py`（`PHASE2_MYSQL_INTEGRATION=1`） | §4.3 引导 + §4.5 门禁 | 证据 Task 2 MySQL 行；E2E 断言 `list_sql_tables` |
| 12 | RAGFlow 助手 | `app/providers/ragflow.py`、`app/tools/knowledge.py` | `test_external_adapters.py`、`test_external_provider_smoke.py`（`PHASE2_RAGFLOW_SMOKE=1`） | §5.2 | 证据 Task 2；E2E 断言 `list_knowledge_assistants` |
| 13 | 主智能体与文件交付 | `app/agent/factory.py`、`app/agent/runtime.py`、`app/tools/files.py`、`app/tools/reports.py` | `test_workspace.py`、`test_file_reader.py`、`test_reports.py`、`test_agent_factory.py`、`test_runtime_events.py`、`test_mock_runtime.py` | `uv run pytest tests/unit/phase2/test_workspace.py tests/unit/phase2/test_reports.py -q` | 证据 Task 3/4；E2E 验证上传内容 + 两份报告 |
| 14 | 后端与前端闭环（FastAPI/WS/React） | `app/api/schemas.py`、`app/api/tasks.py`、`app/api/server.py`、`app/main.py`、`frontend/src/**`、`frontend/e2e/tutorial-workbench.spec.ts` | `test_task_registry.py`、`test_api_contract.py`、`test_websocket_flow.py`、`tests/e2e/phase2/test_tutorial_closure.py`、`frontend/src/**/*.test.tsx` | `uv run pytest tests/ -q`；`pnpm --dir frontend exec vitest run`；`pnpm --dir frontend exec playwright test` | 证据 Task 5/6/7；E2E 全链路（上传→WS→终态→下载） |

验收证据（含真实命令输出与 RED/GREEN 记录）见
[`docs/verification/phase-2-evidence.md`](verification/phase-2-evidence.md)。

## 13. 完整离线验证命令

```bash
uv sync --extra dev --frozen
.venv/bin/python -m pytest tests/ -q
.venv/bin/ruff check app examples tests scripts
.venv/bin/ruff format --check app examples tests scripts
.venv/bin/pre-commit run --all-files
docker compose config
.venv/bin/python scripts/doctor.py --offline
pnpm --dir frontend exec vitest run
pnpm --dir frontend lint
pnpm --dir frontend build
pnpm --dir frontend exec playwright install chromium
pnpm --dir frontend exec playwright test
```

（MySQL 集成与外部 smoke 见 §4.5 / §5，默认跳过，需要时显式开启。）
