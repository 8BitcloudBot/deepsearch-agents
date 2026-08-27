# Codex Prompt: Execute The Phase 4.5 Portfolio Finalization Plan

你现在负责完成 `deepsearch-agents` 的 Phase 4.5 作品集封版修复。

项目目录：

```text
/Users/wxhu/Documents/reasonix/deepsearch-agents
```

唯一实施计划：

```text
docs/superpowers/plans/2026-08-11-phase-4-5-portfolio-finalization.md
```

请先完整读取以下文件，再开始任何修改：

```text
AGENTS.md
docs/README.md
docs/phase-status.md
docs/roadmap.md
docs/phases/phase-4-5-research-showcase.md
docs/superpowers/plans/2026-08-08-phase-4-5-research-showcase.md
docs/superpowers/plans/2026-08-11-phase-4-5-portfolio-finalization.md
docs/superpowers/specs/2026-08-10-knowledge-retrieval-qdrant-local-fastembed-migration-design.md
docs/verification/knowledge-retrieval-migration-evidence.md
```

使用 `executing-plans` skill，严格按照封版计划的 Task 0 到 Task 8 顺序执行，逐项更新
计划中的 checkbox。不要只分析或重新写一份计划；完成允许范围内的代码、测试、文档和
离线验证。

## 本提示词授权的操作

- 修改当前项目中的代码、测试和文档；
- 新增计划明确列出的知识 manifest parser、索引 CLI、测试 fixture 和验收 evidence；
- 运行离线 pytest、Vitest、Ruff、frontend lint/build、`git diff --check`；
- 启动本地 API/frontend，完成桌面和移动浏览器 smoke；
- 使用 pytest 临时目录和非敏感 fixture 完成本地验证；
- 在不输出变量值的前提下，检查真实 smoke 所需配置是否存在。

## 本提示词不授权的操作

- 不调用真实 LLM、Tavily、宿主 MySQL、生产数据或其他外部 Provider；
- 不读取、打印、复制或写入任何 secret 值；
- 不建设正式知识数据，不下载或整理业务文档，不做检索准确率评测；
- 不恢复 RAGFlow 代码、依赖、配置、测试或当前路线表述；
- 不调用子代理、Reasonix 或其他编码模型；
- 不执行 `git add`、commit、push、tag、merge、release、deploy、stash、reset、checkout
  或清理工作树；
- 不覆盖、回滚或删除现有用户修改。

## 执行原则

1. 当前基线固定为 `main` 的 `ce3e2f9` 加现有未提交工作树。先执行 Task 0，确认实际
   状态；如果 SHA 不同或计划依赖的文件不存在，停止并报告，不要猜测或重置。
2. 每个行为修改都执行 TDD：先写聚焦失败测试并确认 RED，再写最小实现并确认 GREEN，
   最后跑受影响回归。不要为了让测试通过而弱化合同。
3. 第一优先级是修复真实业务语义：Web、MySQL、knowledge、uploaded-file 工具必须向
   LLM 返回受限、脱敏、明确标为 untrusted 的来源内容，不能只返回“收集了 N 条”；
   同一 normalized item 必须同时形成 model-visible summary 和 collector evidence。
4. 第二优先级是修复封版可靠性：只保留 DeepAgents 最终 AI answer、增加显式知识索引
   命令、清理被移除的 stale chunks、把知识索引启动异常降级为单来源 limitation。
5. 索引 CLI 只读取用户显式指定的 JSON manifest；禁止目录扫描、OCR、PDF 解析、自动
   corpus 构建和隐式写入 `.data/knowledge-index`。`--validate-only` 不得加载 FastEmbed
   或创建缓存/索引目录。
6. 默认测试不得联网、加载/下载 embedding 模型、读取凭据或调用真实数据源。现有
   `PHASE45_FASTEMBED_SMOKE` 仍是独立 opt-in gate。
7. 所有错误、事件、报告、测试输出和 evidence 都必须脱敏，不暴露 Provider 原始响应、
   本机绝对路径、模型缓存路径和 credential。
8. 不把正式知识库、检索质量、Qdrant Server、TEI、生产并发、Phase 5-8 放入本次范围。
9. 不因为旧历史文档中出现 RAGFlow 字符串就全局替换；只确保当前 runtime、配置、前端、
   测试和 canonical 执行路线不再使用 RAGFlow。
10. 保持用户可见进度更新：每完成一个 Task，汇报改动、测试结果和下一 Task；遇到失败
    先按 `systematic-debugging` 找根因，不要跳过。

## 真实 Provider 门禁

完成 Task 7 Step 1-3 后必须暂停。只汇报以下布尔能力，不得显示环境变量值：

```text
model_configured: true|false
tavily_configured: true|false
mysql_configured: true|false
knowledge_index_available: true|false
upload_fixture_available: true|false
```

然后向我申请是否授权执行这一条真实命令：

```bash
PHASE45_REAL_SHOWCASE_SMOKE=1 PYTHONPATH=. .venv/bin/pytest -q \
  tests/integration/phase4_5/test_real_showcase_smoke.py
```

没有我的明确确认就不得执行。如果能力不全，记录诚实的 capability-based skip，不得伪造
通过结果。即使真实 smoke 未获授权，也继续完成仍可执行的离线门禁和浏览器离线 smoke，
但不得把 P4.5-6 标记为 accepted。作品集 checkpoint 至少需要一次经我明确授权、实际
到达真实 LLM 的 Showcase 运行；只有 capability-based skip 不算封版完成。

## 最终交付

完成允许范围内的工作后，必须给出：

1. Task 0-8 的完成/阻塞状态；
2. 修改文件清单及每项业务效果；
3. 实际执行的测试命令与真实结果；
4. offline、FastEmbed local、real Provider 三个证据分区；
5. 正式知识数据和检索质量仍未建设的明确说明；
6. `git status --short` 与 `git diff --stat HEAD` 摘要；
7. 当前是否达到“作品集/面试可稳定演示”的结论，以及仍阻塞它的具体事项。

不要 commit、push、tag 或 release。最终停在工作树和证据可供我审阅的状态。
