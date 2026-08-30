# RagFlow 概览

> 来源：GitHub infiniflow/ragflow（README，v0.27.1，Apache-2.0）。整理日期 2026-08-30。

## 定位

RAGFlow 是领先的开源 **Retrieval-Augmented Generation（RAG）引擎**，将前沿 RAG 与 Agent 能力融合，为 LLM 构建高质量 context layer。由融合式 **context engine** 与预置 agent 模板驱动，可将复杂数据转化为高保真、生产就绪的 AI 系统。

## 核心特性（Key Features）

- **"Quality in, quality out"**：基于 Deep document understanding（deepdoc）的知识提取，支持复杂格式的非结构化数据；可在"无限 token 的数据干草堆"中找针
- **Template-based chunking**：智能且可解释的模板化分块，提供大量模板选项
- **Grounded citations**：文本分块可视化允许人工干预；关键引用快速查看与可追溯引用（traceable citations）降低幻觉
- **异构数据源兼容**：Word、Slides、Excel、TXT、图片、扫描件、结构化数据、网页等
- **自动化 RAG 工作流**：面向个人与大型企业的编排；可配置 LLM 与 embedding 模型；**多路召回配融合重排（multiple recall paired with fused re-ranking）**；直观 API

## 自托管要求

- CPU >= 4 核；RAM >= 16 GB；磁盘 >= 50 GB
- Docker >= 24.0.0 与 Docker Compose >= v2.26.1
- Python >= 3.13
- 代码执行器（sandbox）功能需要 **gVisor**
- Elasticsearch 前置：`vm.max_map_count` >= 262144（`sudo sysctl -w vm.max_map_count=262144`，重启失效需写入 /etc/sysctl.conf）
- Docker 镜像版本：`infiniflow/ragflow:v0.27.1`（在 docker/.env 的 `RAGFLOW_IMAGE` 变量中切换版本）
- ARM64 平台需按官方指南自建兼容镜像
