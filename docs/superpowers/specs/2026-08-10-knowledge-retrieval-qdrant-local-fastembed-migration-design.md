# Knowledge Retrieval Migration: Qdrant Local + FastEmbed

**状态：** 已实施于当前工作树；验证记录见
[Knowledge Retrieval Migration Evidence](../../verification/knowledge-retrieval-migration-evidence.md)

**适用项目：** `deepsearch-agents`

**目标：** 移除 Showcase 对 RAGFlow 的运行时依赖，改用本地、可复现、低资源的
`Qdrant Local + FastEmbed` 知识检索实现，同时保留未来迁移到 `Qdrant Server + TEI`
的清晰 seam。

## 1. 决策摘要

当前知识来源不需要一个包含文档管理、Assistant、会话、内置问答编排和多服务依赖的
完整 RAG 平台。DeepAgents 已经负责主 Agent、专家 worker、工具调用、答案汇总和引用
交付。知识模块只需要完成：

```text
文档索引 -> chunk embedding -> Top-K 检索 -> 返回带定位的知识片段
```

因此当前采用：

```text
KnowledgeRetriever
  -> Qdrant Local (qdrant-client path mode)
  -> FastEmbed / ONNX Runtime
```

当前 Showcase 默认不再使用 RAGFlow。旧 Phase 2 tutorial 不需要继续证明 RAGFlow
兼容性，旧 RAGFlow provider、SDK、配置、示例和当前路线文案应在本次迁移中清理。

未来若需要多实例、多人并发、批量 embedding 或云部署，只替换 `KnowledgeRetriever`
的 adapter：

```text
KnowledgeRetriever
  -> Qdrant Server + TEI adapter
```

上层 DeepAgents、citation、API、WebSocket、React 和 Markdown/PDF 合同不应感知底层
向量库或 embedding 服务的变化。

## 2. 目标与非目标

### 2.1 目标

- 让本地系统无需启动 RAGFlow、Elasticsearch、Redis、MinIO 等配套服务即可完成知识
  检索 smoke。
- 使用本地持久化 Qdrant collection，支持离线重复启动和固定索引路径。
- 使用 FastEmbed 在 Python 进程内生成 embedding，默认不请求外部模型 API。
- 将知识来源定义为厂商无关的 `knowledge`，不再把 `ragflow` 写入业务合同。
- 返回稳定的 `collection_id`、`document_id`、`chunk_id`、版本和内容摘要，继续接入
  现有 citation collector、claim/evidence、报告和前端来源面板。
- 为未来 Qdrant Server + TEI 保留小而深的 `KnowledgeRetriever` 接口。
- 清理当前 canonical 文档、配置、依赖、前端标签和测试中的 RAGFlow 路线，避免新
  Agent 把历史实现误当成当前架构。

### 2.2 非目标

- 本轮不建设最终知识库数据，不下载、整理或批量导入新的技术文档。
- 本轮不测量真实检索准确率，不生成知识库质量结论。
- 不实现 OCR、复杂 PDF 版面解析、表格理解或图谱检索。
- 不引入第二套 Agent 框架，不让知识 adapter 负责答案生成。
- 不实现 Qdrant Server、TEI、云部署、集群、高可用或多租户管理。
- 不保留“为了教程兼容”而存在的 RAGFlow 运行时代码。

## 3. 迁移前系统事实（历史背景）

本节记录 2026-08-10 设计时的迁移输入，仅用于解释决策，不是当前执行指导。当时
P4.5 Showcase 已经有统一的来源定位、引用交付和 React 展示合同，但知识适配器仍把
RAGFlow 当成具体业务来源：

- `KnowledgeProvider` 以 `assistant_name + ask` 为中心；
- RAGFlow adapter 会列出 Assistant、创建 session、提问并删除 session；
- Showcase 配置只允许 `KNOWLEDGE_PROVIDER=ragflow`；
- locator 和前端 source kind 直接使用 `RAGFlowLocator` / `ragflow`；
- `pyproject.toml` 直接依赖 `ragflow-sdk`；
- README、Phase 4.5 文档、运行计划和测试 fixture 把 RAGFlow 写成当前路线。

这些是本次迁移的清理对象，不代表仍需维持兼容。

原始教程提供的是小规模教学数据，不是固定的技术文档评测集：

- 5 份示例 PDF，共 254 页、约 20.18 MB；
- 内容是电商和金融行业报告；
- MySQL 是制药公司模拟库：`drugs` 50 行、`inventory` 150 行、`sales_records`
  100 行，共 300 行；
- 原教程没有提交固定 chunk manifest、gold 检索问题或召回准确率合同。

本项目当前不复制原教程的 RAGFlow 部署路线，也不把这些示例 PDF 自动转成新的正式
知识库数据。知识数据建设另行立项。

## 4. 目标架构

```text
Research request
  -> DeepAgents main agent / knowledge worker
  -> KnowledgeRetriever.search(query, filters, limit)
  -> Qdrant Local collection
  -> FastEmbed embedding
  -> KnowledgeChunk[]
  -> citation collector (collection/document/chunk locator)
  -> main agent synthesis
  -> WebSocket / API / React / Markdown / PDF
```

知识模块只返回证据片段，不返回“另一个模型生成的最终答案”。这样可以避免：

- RAGFlow Assistant 与 DeepAgents 主 Agent 重复生成；
- 临时 session 造成额外状态和清理路径；
- 引用指向二次生成文本而不是原始 chunk；
- Provider 故障与 Agent 失败混在一起。

### 4.1 稳定接口

建议在 `app/providers/contracts.py` 或 Showcase 专用 contracts 中定义：

```python
@dataclass(frozen=True)
class KnowledgeChunk:
    collection_id: str
    document_id: str
    chunk_id: str
    title: str
    content: str
    score: float
    version: str
    source_uri: str | None = None
    section_path: str | None = None


class KnowledgeRetriever(Protocol):
    def search(
        self,
        query: str,
        *,
        collection_id: str,
        limit: int = 8,
        document_version: str | None = None,
    ) -> tuple[KnowledgeChunk, ...]: ...


class KnowledgeIndexer(Protocol):
    def index_documents(self, documents: Sequence[KnowledgeDocument]) -> IndexReport: ...
```

`KnowledgeRetriever` 是运行时外部 seam；`KnowledgeIndexer` 只被离线索引脚本使用，
不在每次研究请求中隐式修改 collection。

接口不暴露：

- Assistant 名称；
- session ID；
- RAGFlow SDK 对象；
- embedding 服务 URL；
- 任意 API key；
- provider-specific 原始响应。

### 4.2 Qdrant Local adapter

- 使用 `qdrant-client` 的 `QdrantClient(path=...)` 本地持久化模式；
- collection 名称、索引路径、向量维度、距离函数和 embedding model version 必须显式
  配置；
- 默认距离使用 cosine；
- payload 至少包含 `collection_id`、`document_id`、`chunk_id`、`title`、`version`、
  `section_path`、`content` 和 `content_sha256`；
- point ID 必须由稳定的 document/chunk identity 派生，重复索引必须幂等；
- 运行时只读检索，索引构建由显式脚本完成；
- 索引目录必须位于项目运行数据目录并加入 `.gitignore`，不得提交向量、私有文档或
  embedding 模型缓存。

### 4.3 FastEmbed adapter

- 使用 FastEmbed 的 Python/ONNX Runtime 实现，不启动单独 embedding 服务；
- embedding 模型、维度、版本和 query/document 前缀规则必须集中配置；
- 默认使用一个 FastEmbed 支持的中英多语小模型，例如
  `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`；已在锁定的
  FastEmbed 0.8.0 内置模型清单中核对其支持性（384 维、无需 query/document 前缀），不得
  把未验证的模型能力写成已测量效果；
- 模型只在首次索引或首次查询时加载，并允许本地缓存；
- 任何模型下载都不属于默认测试路径，离线测试必须使用 fake embedder；
- 不把 FastEmbed 的模型名称、内部异常或本地绝对路径写入用户响应和 citation。

### 4.4 未来 Qdrant Server + TEI seam

未来 adapter 可以将两个职责拆分：

```text
KnowledgeRetriever
  -> TEI HTTP embedding adapter
  -> Qdrant Server client
```

这一阶段只需要保留接口和配置兼容性，不实现服务。迁移时不得改变
`KnowledgeChunk`、locator、citation 或 Agent tool contract。

## 5. 配置合同

当前 Showcase 的配置应改为厂商无关字段：

```dotenv
SHOWCASE_SOURCES=web,mysql,knowledge,uploaded-file
KNOWLEDGE_PROVIDER=qdrant-local
KNOWLEDGE_INDEX_PATH=.data/knowledge-index
KNOWLEDGE_COLLECTION=deepsearch-showcase-v1
KNOWLEDGE_EMBEDDING_PROVIDER=fastembed
KNOWLEDGE_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

约束：

- `knowledge` 未在 `SHOWCASE_SOURCES` 中声明时，不读取知识库配置、不加载模型；
- `qdrant-local` 必须要求合法的相对索引路径或显式允许的运行数据路径；
- collection 的向量维度必须与模型实际输出一致；
- embedding fingerprint 必须包含模型名、FastEmbed 依赖版本、向量维度、距离函数和
  query/document 前缀规则；
- model/dependency/distance/chunking fingerprint 变化时建立新 collection 名称，不静默
  覆盖旧索引；
- 默认 app profile 和离线测试不得触发模型下载或写入索引。

本轮不要求配置真实知识文档路径；索引脚本可以先对空 collection 或测试 fixture
运行，并明确“知识数据尚未建设”。

## 6. 引用和业务行为迁移

### 6.1 来源合同

将 `SourceKind.RAGFLOW` 替换为通用 `SourceKind.KNOWLEDGE`，将
`RAGFlowLocator(dataset, document, chunk)` 替换为
`KnowledgeChunkLocator(collection, document, chunk)`。

这是 wire contract 的破坏性变化。当前 live citation/source schema 必须显式升级主版本，
并同步更新后端序列化、前端严格 parser、fixture、报告和 API/WebSocket contract tests。
不得在原 schema 版本下静默把 `ragflow` 改成 `knowledge`。冻结的 Phase 4 离线历史
fixture 不原地改写；当前 Showcase 的新 canonical schema 只接受 `knowledge`，不保留
双读兼容。

前端显示“Knowledge base”或中文“知识库”，不显示 Qdrant、FastEmbed 或旧 RAGFlow
作为业务来源名称。底层实现信息只出现在 health/debug/证据元数据中。

### 6.2 Agent 工具

将 `showcase_ask_knowledge(assistant_name, question)` 改为类似：

```text
showcase_search_knowledge(query, collection_id?, limit?)
```

工具返回受限数量的知识片段摘要和定位，不允许模型传入任意本地路径、collection
路径或 embedding 参数。collection 白名单由服务端配置决定。

### 6.3 错误与降级

- 索引目录不存在：返回结构化 `knowledge-unavailable`，不自动创建空结果冒充成功；
- collection 不存在：返回 `knowledge-unavailable`，并说明需要运行索引脚本；
- embedding 模型不可加载：返回 `knowledge-unavailable`，不访问外部 Provider；
- 检索无命中：返回空 evidence 和 `no-evidence` limitation；
- 单条 chunk metadata 无效：跳过该 chunk，记录脱敏 limitation，不泄露原始 payload；
- 知识来源不可用时，Web、MySQL、上传文件仍可独立运行。

## 7. 代码、依赖和文档清理范围

实现者必须先建立 RAGFlow 引用清单，再按引用分类处理。不得用全局替换破坏历史语义。

### 7.1 必须移除或替换的当前实现

- `ragflow-sdk` 依赖和 lockfile 记录；
- `app/providers/ragflow.py`；
- `app/ragflow/` 下的配置、示例和运行时代码；
- RAGFlow 专用 provider factory 分支；
- `KnowledgeProvider` 的 Assistant/session/ask 语义；
- `RAGFlowLocator`、`normalize_ragflow_chunk` 和 provider-specific source kind；
- RAGFlow 专用 fixtures、integration smoke 和测试环境变量；
- `.env.example` 中的 RAGFlow 配置；
- 前端“RAGFlow 助手”标签、类型、样式和测试名称。

用户已明确授权替换和删除 RAGFlow 专用路线，因此仅属于 RAGFlow 的未提交实现可以在
Task 0 快照后删除或重写。其他未提交修改仍必须保留；若一个文件同时包含 RAGFlow 和
无关用户改动，实施者必须逐段合并，不能覆盖整文件。

### 7.2 必须更新的当前 canonical 文档

至少检查并更新：

- `AGENTS.md`；
- `docs/README.md`；
- `docs/phase-status.md`；
- `docs/roadmap.md`；
- `docs/phases/phase-4-5-research-showcase.md`；
- 当前 Phase 4.5 design/plan；
- README 和 `.env.example`；
- 当前 verification/evidence 文档。

当前路线统一描述为：

```text
Tavily Web / MySQL / local knowledge retrieval / uploaded files
```

历史文档可以保留“原教程曾使用 RAGFlow”的事实，但必须明确标注为历史背景，不能出现在
当前执行入口、当前技术栈、当前启动命令或当前验收标准中。若历史文档会被 AGENTS 或
docs index 默认加载，应改成指向本决策，或移入明确的 archive/history 区域。

### 7.3 不应清理的内容

- 不删除原教程外部链接和来源说明；
- 不重写与当前迁移无关的 Phase 0-4 业务合同；
- 不删除已验证的 DeepAgents、Tavily、MySQL、上传文件、citation、报告和前端能力；
- 不把本轮尚未建设的知识数据写成已存在；
- 不为了消除字符串而删除有价值的历史证据，需保留历史事实但隔离其当前影响。

## 8. 验收标准

### 8.1 静态和依赖

- `rg` 检查当前 canonical 文档、代码、配置和前端不再出现 RAGFlow 运行路线；
- `ragflow-sdk` 不在 `pyproject.toml`、锁文件或运行时 imports 中；
- 旧 RAGFlow provider、配置和 factory 分支已删除；
- `KNOWLEDGE_PROVIDER=qdrant-local`、`knowledge` source kind 和新 locator 在代码与文档中
  口径一致；
- Git diff 不包含私有文档、模型缓存、绝对路径、凭据或本地 Qdrant 数据。

### 8.2 自动化

- fake embedder + temporary Qdrant Local path 可以创建 collection 并检索；
- 相同文档重复索引不产生重复 point；
- collection/model/chunk fingerprint 变化会拒绝混写或创建新 collection；
- query 返回稳定排序和稳定 `collection/document/chunk` identity；
- invalid metadata、越权 collection、绝对路径和路径 traversal 被拒绝；
- knowledge unavailable 时，其他来源仍能独立工作；
- citation、API、WebSocket、报告和前端测试改用通用 knowledge fixture；
- 默认离线测试不会下载模型、联网或写入真实索引。

### 8.3 真实本地 smoke

只在实现者明确准备测试 fixture 后运行：

1. 用索引脚本将一小组非敏感 fixture 文档写入临时 Qdrant Local path；
2. 用一个固定问题检索；
3. 检查返回 chunk、稳定 locator、citation 和前端展示；
4. 删除临时目录，不把索引提交到 Git。

本轮 smoke 只证明 adapter 和引用链可用，不证明最终知识库质量，也不代表真实数据已
建设。

## 9. 未来升级路线

```text
当前：Qdrant Local + FastEmbed
  -> 完成本地 showcase smoke 和作品集 checkpoint

未来有真实扩展需求时：
  -> 保持 KnowledgeRetriever interface
  -> 增加 TEIEmbeddingAdapter
  -> 增加 QdrantServerRetriever
  -> 做延迟、吞吐、内存和失败率对照
```

只有出现以下需求才升级：多实例共享、多人并发、数万以上 chunk、批量 embedding、云
部署或需要独立模型服务监控。升级前不应为未来服务提前引入 Docker、TEI 或 Qdrant
Server。

## 10. 完成后的准确表述

完成本迁移后可以说：

> Deepsearch 使用 DeepAgents 编排多来源研究流程，采用 Qdrant Local 和 FastEmbed
> 提供本地知识库向量检索；检索模块通过厂商无关的 KnowledgeRetriever 返回带
> collection/document/chunk 定位的证据片段，并与 Tavily、MySQL、上传文件、引用校验和
> Markdown/PDF 交付统一集成。当前目标是可复现的本地作品集演示，不宣称生产级知识库
> 规模或检索准确率。

不能说：

- 当前仍使用 RAGFlow；
- 已有 RAGFlow 生产知识库；
- 已完成知识库质量评测；
- Qdrant Local 天然比 RAGFlow 更准确；
- FastEmbed 已证明真实业务召回率达到某个百分比。
