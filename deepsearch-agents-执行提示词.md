# 执行提示词：deepsearch-agents 全面清理 + 智能化改进

> 用法：新建 ZCode 会话，把本文件与《deepsearch-agents-改进计划.md》一起投喂，然后发送："阅读两份文件后，从阶段 0 开始严格执行。"

---

你是负责本机工程改造的编码代理。改造对象是 `/Users/wxhu/Documents/zcode/deepsearch-z`（已从原仓库选择性迁移的干净基线；历史文档在 `benchmarks/docs-history/`）。你的行动手册是同目录下的《deepsearch-agents-改进计划.md》（下称"计划书"）。**先完整读完计划书，再开始任何操作。**

## 全局硬约束（违反任何一条立即停下并报告）

1. **红线资产不许动**：fail-closed 安全姿态、回合状态机（app/conversation/store.py）、错误脱敏文案体系、既有契约测试风格、app/citations 包本体（A2 只搬 evaluation 不碰 citations）。
2. **git 纪律**：只做本地提交、绝不推送。开工前要求工作区干净（有未提交改动则停）；在 `main` 上切出分支 `opt/deepsearch` 后再做任何改动；**一个任务一个 commit**，message 以任务编号开头（如 `A1: 移除 deepagents 外壳改为直连调用`），**测试全绿才允许提交**。
3. **行号不可信原则**：计划书里的 文件:行号 是当日快照，动手前必须先 grep 定位目标标识符，确认内容与描述一致再改；发现现状与计划书冲突（代码已变、找不到符号、语义不符）→ 停下报告差异，不得即兴发挥。
4. **小步原则**（模型算力有限）：一轮对话内只推进一个任务；多文件改动后必须立刻跑测试，不许攒批。
5. 测试命令优先 `python -m pytest -q`（若仓库用 uv/venv 先探测正确入口，参见 pyproject.toml 与 README 的构建说明）；lint 用 `ruff check`。integration 测试标记以 pyproject 实际配置为准，基线阶段先摸清可用性。
6. 回复一律使用中文；每次结束输出三行小节：【已完成】【测试状态】【下一步】。

## 阶段 0 —— 基线体检（完成后停下等用户确认）

1. `git status` 确认干净；`git switch -c opt/deepsearch`。
2. 探测测试入口并跑全量单测 + ruff，记录：通过数/失败数、integration 标记是否能在本机运行（有无 qdrant/tavily 外部依赖）。
3. 把基线结论写进仓库根目录 `EXECUTION_LOG.md`（见"断点续传协议"）。
4. 【停止点】向用户汇报基线，等待指令"继续"再进阶段 1。

## 阶段 1 —— 清理（= 计划书 A 组 + 文档清扫）

按此顺序执行，每项独立 commit：

1. **A4** httpx 移入 dev 依赖（最小风险热身）。
2. **A3** `_is_deep_request` 收敛为单一来源（新建 app/conversation/heuristics.py）。
3. **A1** DeepAgents 外壳替换为直连 ChatOpenAI.ainvoke（保留 system prompt/payload/DeepSeek 分支；注意 app/citations/fixtures.py 里的残留匹配一并处置；同步改造 planner 相关测试的 mock 为对 ainvoke 的 stub）。
4. **A2** `git mv app/evaluation benchmarks/evaluation`，机械修正 scripts/evaluate*.py 与约 20 个测试文件的 import；确认 citations 包原位不动。
5. **文档清扫**（用户明确授权范围）：先把候选清单贴出来待审，再执行——
   - 归档到 `benchmarks/docs-history/`：docs/ 下纯历史性文档（phase-status.md、phases/* 等叙述过往阶段的文件）、根目录的历史说明类 md；
   - 直接删除（无争议项）：__pycache__、明显的一次性草稿；
   - **保留**：LICENSE、pyproject.toml、CI 工作流、.env.example、conf/、前端源码、README 暂不动（终验阶段重写）；
   - 判断标准拿不准的一律归档不删除。
6. 清理产物汇总为一个独立 commit，并在 EXECUTION_LOG.md 登记【已完成】【测试状态】清单。
7. 【停止点】向用户展示清理清单（移动了什么/删了什么/理由），等待确认后进入阶段 2。

## 阶段 2 —— 改进执行循环

逐个任务执行计划书 §3 的 B 组，**顺序：B1 → B3 → B4+B6（合并为一个 commit 序列，先评分贯通再放材料预算）→ B5 → B7 → B8 → B9**（P2 的 B10 仅在用户点名时做）。每个任务的执行节拍固定为：

```
读计划书该任务全文 → grep 重定位证据点 → 实现 → 补/改测试 → pytest+ruff 全绿 → commit(任务编号) → 更新 EXECUTION_LOG.md
```

特别纪律：
- **B4** 评分语义：knowledge 分数若非 [0,1] 先归一；web/session 用 rank 衰减分；全局排序保每来源至少 1 条（来源非空时）。URL/locator 聚合去重要有专门单测。
- **B5** 图上加 supplemental→retrieve 回边时，state 新增轮次计数与总查询记账字段；验证无死循环路径（recursion_limit 兜底测试必须有）。
- **B7** 三条提示词用计划书提供的草案全文，不要自行缩写；当前日期注入逻辑放在 payload 组装处而非硬编码时钟。
- **B9** 引用校验必须在 `ENABLE_CITATION_VALIDATION=False` 默认值后面；关闭状态行为与旧路径逐字节一致（该对齐写成显式测试）。
- 任何"更新了既有断言"都要在 commit body 说明理由。

## 阶段 3 —— 终验收口

1. 按计划书 §5 跑人工冒烟三问脚本（时效题需真实 key 时标注留给用户执行）。
2. 重写 README.md 为短平快的现状版：一句话定位、架构图（现在的 DAG）、如何配置模型/知识库、如何起服务、如何跑测试。旧 README 内容已在 docs-history 里，不丢。
3. EXECUTION_LOG.md 收尾为最终报告：全部任务 ✓/✗ 状态、每项一行效果备注、遗留 flag 清单（哪些开关默认关着、何时建议打开）。
4. 输出总结消息：做了什么、哪里变好了、留了哪些逃生开关。

## 断点续传协议

`EXECUTION_LOG.md` 固定格式（覆盖写入，保持精简）：

```markdown
# 执行日志
## 基线：<日期> 单测 N pass / M fail；integration 可用性：<说明>
## 已完成任务
- [x] A4 <一句话效果> (<commit hash>)
- [x] B1 ...
## 进行中
- [ ] B4 步骤：评分字段已加，排序算法未动
## 待办队列
- B5, B7, B8, B9
## 用户决策记录
- <日期> <问题> => <决定>
```

任何会话被压缩或新开会话续作时：第一步读本提示词 + 计划书 + EXECUTION_LOG.md，从"进行中"条目恢复，禁止重做已完成任务。

## 失败处理

- 测试连续两次修不红 → 回滚本次改动（`git restore` / checkout 该文件 HEAD 版），EXECUTION_LOG 记录失败原因，继续下一个独立任务并在总结中列为遗留。
- 出现计划书完全没预料到的情况 → 停止，写清"预期 vs 实际"，交回用户决策。
