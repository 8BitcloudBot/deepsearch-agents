# RagFlow 更新时间线与进阶笔记（个人）

> 来源：GitHub infiniflow/ragflow（README Latest Updates 节）。整理日期 2026-08-30。本文件为个人笔记库内容。

## Latest Updates 时间线（倒序）

- **2026-06-15**：支持多聊天渠道接入——Feishu、Discord、Telegram、Line 等
- **2026-04-24**：**支持 DeepSeek v4**
- **2026-03-24**：RAGFlow Skill 上架 OpenClaw（clawhub.ai/yingfeng/ragflow-skill）——通过官方 skill 访问 RAGFlow 数据集
- **2025-12-26**：为 AI agent 支持 'Memory'
- **2025-11-19**：支持 Gemini 3 Pro
- **2025-11-12**：支持从 Confluence、S3、Notion、Discord、Google Drive 同步数据
- **2025-10-23**：支持 MinerU 与 Docling 作为文档解析方法
- **2025-10-15**：支持可编排的 ingestion pipeline
- **2025-08-08**：支持 OpenAI GPT-5 系列模型
- **2025-08-01**：支持 agentic workflow 与 MCP
- **2025-05-23**：Agent 增加Python/JavaScript 代码执行器组件
- **2025-03-19**：支持用多模态模型理解 PDF/DOCX 内的图片

## 生态关联

- OpenClaw 同时基于 Pi SDK 构建——RAGFlow 的 OpenClaw skill 意味着 Pi 生态可以直连 RAGFlow 数据集
- 对 DeepSeek v4 的支持（2026-04-24）早于 DeepSeek Harness 的 Developer Preview 发布

## 部署补充

- 镜像发布于 Docker Hub：`infiniflow/ragflow`（当前 v0.27.1）
- 云服务：cloud.ragflow.io；文档：ragflow.io/docs/dev/
- Roadmap 在 GitHub issue #12241 维护
