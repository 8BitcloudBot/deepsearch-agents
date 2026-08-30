# DeepSeek Harness 进阶笔记（个人）

> 来源：DeepSeek 官方博客、GitHub deepseek-ai/deepseek-harness。整理日期 2026-08-30。本文件为个人笔记库内容。

## 核心公式

官方给出的概念公式：**Agent = Model + Harness**——模型是 agent 的"灵魂"，harness 让模型理解环境、使用工具、在真实环境中持续工作。

## Trajectory 视图与事件流

- append-only session log 是唯一事实源；Trajectory 视图支持**按来源**检查每次 context injection
- resume（恢复）、fork（分叉）、search（检索）、replay（重放）四种操作全部构建在同一事件流之上——没有独立的存储路径
- 第三方报道指出 Harness 可以调用 Claude Code 或 Codex 作为 sub-agent（插件互操作）

## 定位参考

第三方评测将其定位为"把 V4 系列模型变成可靠自主编码 agent 的运行时"，即补齐 "model-plus-runtime gap"（模型与运行时之间的空档）。

## 仓库与文档

- 文档站：deepseek-harness.github.io/deepseek-harness（en/guide/quickstart）
- AGENTS.md 自述为 "all-plugin Cordis agent harness"，架构文档在仓库 `docs/architecture.md`
- Cordis 论文：arxiv.org/abs/2608.25512
- 注意：官方 Developer Preview 公告中未出现 V4 系列具体模型版本号，仅泛称 subagents 能力
