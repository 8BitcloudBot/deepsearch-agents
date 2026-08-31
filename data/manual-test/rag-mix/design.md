# 实验设计：RAG 混合分库真实场景测试床

> 目的：以四份真实技术文档（PI Agent / Codex harness / DeepSeek Harness / RagFlow）
> 在全局库与个人库双库并存的真实数据分布下，发现问题、找优化点与最佳实践。
> 状态：**基础条件已构建并入库，查询测试暂不执行**（剧本见 queries.md）。

## 分库方案（每文档拆两半）

| 主题 | 全局库（主语料 collection 追加） | 个人库（uploads-{user_id}） | 拆分逻辑 |
|---|---|---|---|
| PI Agent | pi-agent-overview（定位/哲学/扩展机制/LLM 支持/安装/运行模式） | pi-agent-notes（树 session/steering/SYSTEM.md/第三方扩展/OpenClaw） | 概述与稳定事实→全局；会话细节与生态动态→个人 |
| Codex | codex-harness-overview（定位/Rust 架构/安装/认证/MCP/集成） | codex-harness-notes（沙箱审批入口/配置分层 requirements.toml/下载源回退/docs 速查） | 公开入门路径→全局；运维与环境细节→个人 |
| DeepSeek Harness | deepseek-harness-overview（Preview/全插件/Cordis/四模式/追溯/安装） | deepseek-harness-notes（公式/Trajectory/生态关联/仓库补充） | 官方核心公告→全局；解读与外围→个人 |
| RagFlow | ragflow-overview（定位/五特性/自托管要求） | ragflow-notes（更新时间线/OpenClaw 关联/部署补充） | 稳定特性→全局；时间线与生态→个人 |

入库结果（2026-08-30 实测）：全局 53 chunks 追加注入（ragmix-* 前缀）；
个人库 regression-ragmix 用户 4 文档 44 chunks（12/10/14/8）。

## 双库召回预检（构建验证，非正式测试）

- 全局：3/3 查询 top1 命中对应 ragmix-* 文档，绝对分 0.41-0.89
- 个人：3/3 查询命中对应个人文档，0.44-0.71
- 结论：两库注入有效、绝对分语义下判据可区分

## 预期考察点（2026-08-31 执行后已回填）

> 执行记录：18 回合首轮 + 6 回合定向重跑 + 2 次 X1 复验（脚本 /tmp/ragmix_run.py，
> 结果 /tmp/ragmix_results.json）。修复 2 项、确认问题 4 项、最佳实践 2 项。

### 考察点 1：跨库召回路由 → **修复后通过**
首轮 personal=0（测试床缺陷：入库 user_id 与引擎回合 uuid 错位）；
重灌后个人库证据出现 11 次，R4t2/X1 出现跨库并存（deepseek-harness-notes
+ deepseek-harness-overview 同回合）。A1 绝对分语义下两库公平竞争成立。

### 考察点 2：跨主题干扰 → **冻结语料干扰已修复（R2），链路残余三层**
修复链：① ragmix-* 迁出主库至 shared 业务库（uploads/shared 用户），
CombinedKnowledgeRetriever 聚合召回——S4 的 FastEmbed/Ragas 冻结干扰消失；
② 切块修复：标题行被切成孤立 chunk（"## 自托管要求"无内容语义），
已合并标题与紧随内容；③ uploads 阈值独立标定 0.25（规格型内容天然低分）。
**遗留（S4 仍缺硬件 chunk）→ 已修复（L2，2026-08-31）**：
_select_evidence 增加 uploads 系（ev-knowledge-upload- 前缀）保底 2 条
配额——S4 复验必含 2/4（4 核/16 GB 完整呈现），硬件链路全通。
**S3 幻觉 → 已根除（L3 规则 9 + L1 裁剪 + citation 校验组合）**：
忠实度提示词增补规则 9（枚举类问题只列证据可支撑条目）后，模型首次
如实回答"证据仅支持其中部分信息，未能提供完整清单"，零编造，
limitations 主动列出曾试图编造的条目。五次编造 → 零编造。
另：shared 库内四主题互为稀释（单主题子库可再分）仍为可选优化。

### 考察点 3：多轮承接 → **通过**
R2-t2/R3-t3 承接前轮主语（"它/那"指代正确）；R3-t3 必含 3/3。
R4 四轮三主题轮换后总结题（t4）回答正确综合四者分工。

### 考察点 4：轮换抖动 → **未发现回环异常**
18+8 回合中 review 回环消耗正常，未出现把已覆盖内容当缺口的循环。

### 考察点 5：个人库覆盖语义 → 未专项验证（notes 未重传），遗留。

### 执行中发现的新问题（按严重度）
1. **【已修复·commit 本轮】planner 超限硬失败**：三主题对比题下模型稳定输出
   3 条知识库查询（每主题一条，语义合理）超出合同上限 2 → TurnResearchPlan
   ValueError → 整轮失败（X1 两次失败 + 三次复现 kq=3 铁证）。
   修复：解析处截断到 3/2/3 上限降级，敌意测试钉死。
2. **【待修】综合器伪覆盖幻觉（S3 两次复现）**："四种运行模式"回答编成
   Web/CLI/API/插件——正确 chunk（section-0010）在库且切块完好，但综合器
   引用稀疏（仅引 1 条 notes）且忠实度失败。方向：引用完整性约束/忠实度校验。
3. **【待修】planner 偶发 JSON 漂移无重试**：首轮 X1 单次漂移整轮挂
  （synthesize 有 2 次重试，plan 无）。方向：plan 补 1 次重试。
4. **【判据教训】必含词判据对中文改写敏感**（树状/树形、2026-03-24/2026 年
   3 月 24 日）——判据应用事实词而非形式词；evidence cited 统计≠检索池统计。

1. **跨库召回路由**：X1-X3 与 R3-3/R4-4 中，evidence 是否同时出现主库与个人库来源；
   个人库/主库分数语义在 A1 修复后是否公平竞争
2. **跨主题干扰**：四主题与冻结语料（134 chunks）同库，查询"pi 扩展机制"时
   冻结语料的 LangGraph chunks 是否挤占 top6/8 配额（干扰度量化）
3. **多轮承接**：R2/R3/R4 轮换中 recent_history 是否避免重复检索已答主题、
   追问是否正确绑定前轮实体（如"它"的指代）
4. **轮换抖动**：3/4 轮换库时 reviewer 的 uncovered 判定与补充查询是否
   误把已覆盖内容当缺口（回环预算消耗是否合理）
5. **个人库更新语义**：同名 notes 文件重传覆盖后，旧 chunk 是否被正确清除（delete_documents 路径）

## 执行方式

- 入库（幂等）：`uv run --extra dev python data/manual-test/rag-mix/ingest.py`
- 查询执行：按 queries.md 剧本，基于 scripts/regression_e2e.py 的引擎装配模式扩展
- 每条记录：回答全文、evidence 来源分布、耗时/首字、limitations、判据 PASS/FAIL
