# DeepSeek Phase 2 Execution Prompt

> **Historical execution prompt:** do not use as the current task queue. Read
> [`docs/phase-status.md`](../../phase-status.md) and
> [`docs/phases/phase-2-tutorial-parity.md`](../../phases/phase-2-tutorial-parity.md) first.

你将在仓库 `/Users/wxhu/Documents/reasonix/deepsearch-agents` 中执行 Phase 2（Tutorial Parity）。

唯一实施依据是：

1. `docs/superpowers/plans/2026-07-29-agent-engineering-research-copilot-phase-2-plan.md`
2. `docs/superpowers/specs/2026-07-28-agent-engineering-research-copilot-design-v3.md` 中 Section 8、9、11.1、11.1.1、20.1.1、21、22、23、24 的 Phase 2 相关约束
3. `docs/adr/0002-deepagents-version-and-api-surface.md`
4. `docs/phase-status.md`
5. `docs/verification/phase-1-evidence.md`
6. `docs/verification/phase-1-closure-evidence.md`

先完整读取上述文件和当前 Git 状态，再使用 `executing-plans` 按精确计划逐 Task 执行。不要根据教程记忆猜 API，也不要复制上游源码。

执行纪律：

- 只实施 Phase 2，不开始 Phase 3。
- 严格按 Task 0 到 Task 7 顺序执行；每个 Task 先更新状态、先写 RED 测试并保存真实失败证据，再做最小实现、跑 GREEN、更新 evidence、使用显式路径提交，然后停止检查该 Task 是否满足计划。
- 不得更改 Locked Interfaces 中的文件职责、类型名、工具名、事件字段、HTTP/WebSocket 路径、provider mode、artifact 路径语义或 commit 边界。
- Task 0 必须把本计划和本提示词一并纳入显式提交；不得让它们继续未跟踪并在最终伪称工作树 clean。
- 不得自行新增依赖、服务、Agent、路由、事件字段、数据库表、前端面板或后续阶段能力。
- 离线测试必须使用确定性 mock，不得访问模型、Tavily、RAGFlow 或宿主 MySQL。
- mock、Compose MySQL、真实模型、真实 Tavily 和真实 RAGFlow 的证据必须分别标注；没有执行的真实 smoke 只能写 skipped/not run，不能写 passed。
- Structured Data Agent 只允许计划规定的受控只读接口；不得实现通用 Text-to-SQL。
- MySQL 必须同时通过 sqlglot AST 策略和 `tutorial_reader` 数据库权限限制。保留现存 volume，显式执行计划中的幂等 bootstrap；禁止 `docker compose down -v`、删卷或用 root 账号运行 provider。
- Provider mock/real 状态只能读取 `ProviderBundle` 的显式 mode 字段，不得用类名、`isinstance()` 或返回内容猜测。
- Phase 2 只有一个事件实现：直接使用具体 `InMemoryEventBus`，不得新增 `EventSink`/`EventSource` 协议。它只提供当前进程内的单调序列和 live-only 订阅，不保存或暴露事件历史，不得加入 `for_thread()`、replay cursor、断线补发或持久化。
- 只允许一个 `ContextVar[SessionContext]`。`RuntimeRequest` 固定为 `query + context`，不得重复携带 `thread_id`、`upload_dir` 或 `output_dir`；运行时路径只从 `context.workspace` 获取。
- `TaskRegistry` 是 `task_started` 和三个 terminal event 的唯一发出方；runtime 不得发 task lifecycle event。每次运行必须且只能有一个 terminal。
- `{type:"pong"}` 是独立 heartbeat 消息，不得伪装成、保存为或渲染成 `TutorialEvent`。
- 390px 响应式验收必须由计划中的 Playwright Chromium 测试完成；不得用 jsdom/Vitest 结果替代真实布局证据。
- 不得暴露或提交密钥、Cookie、`.env`、数据库 volume、用户文件、生成报告、绝对服务器路径或完整外部响应。
- 禁止 `git add .`、`git add -A`、amend、rebase、force push、历史重写和删除用户数据。
- 不得运行会改写 baseline 时间戳的 `detect-secrets scan --baseline`；安全门禁使用 pre-commit hook。
- 遇到计划的 Required Stop Conditions，立即停止当前 Task，把命令、退出码、最小错误摘要和已尝试诊断写入 `docs/verification/phase-2-evidence.md`，然后请求用户决策。不得自行扩大范围。

用户已在 2026-07-29 明确授权执行 Phase 2。开始编码前先输出以下起始快照，但输出后无需再次等待确认，直接执行 Task 0：

1. 当前 HEAD、分支、工作树状态和 prerequisite tag；
2. Task 0 将修改的精确文件清单；
3. Task 0 的 RED/GREEN 命令；
4. 说明两份 planning artifact 当前是否未跟踪，并确认将在 Task 0 以显式路径纳入提交；
5. 确认快照输出前未开始代码修改，然后立即开始 Task 0。

不要再询问是否执行 Phase 2；本提示词本身携带已确认的执行授权。全部 Task 完成时使用以下固定格式汇报并立即停止：

```text
Phase 2 实施完成，等待用户独立验收

1. Task 0-7 状态与 commit SHA
2. 修改文件清单及每个文件的职责
3. RED/GREEN 证据：命令、退出码、passed/skipped 数量
4. 教程第 8-14 章逐章映射与证据路径
5. mock 闭环、Compose MySQL、真实模型/Tavily/RAGFlow 分项结果
6. API、WebSocket 和 artifact 请求/响应样例
7. preserved-volume MySQL bootstrap、只读账号 SELECT/拒绝 INSERT 证据
8. Node 22 的 Vitest、Playwright Chromium、lint、build 结果
9. 全量 gate 和 pre-commit 结果
10. git status、target tag 查询和 Phase 2 commit 列表
11. 已知限制或 blocker；没有则写“无”

当前状态必须是 awaiting_user_acceptance。
不得创建 v0.1-tutorial-parity tag。
不得开始 Phase 3。
```
