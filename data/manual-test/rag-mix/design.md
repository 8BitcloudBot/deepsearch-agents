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

## 预期考察点（执行后回填）

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
